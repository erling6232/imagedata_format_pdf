"""Read/Write PDF files
"""

# Copyright (c) 2022-2025 Erling Andersen, Haukeland University Hospital,
# Bergen, Norway

import logging
import numpy as np
import pydicom
from pydicom.uid import UID

import imagedata.formats
from imagedata.formats.abstractplugin import AbstractPlugin

logger = logging.getLogger(__name__)


class PDFPlugin(AbstractPlugin):
    """Read PDF files.
    Writing PDF files is not implemented."""

    name = "pdf"
    description = "Read PDF files as encapsulated PDF."
    authors = "Erling Andersen"
    version = "1.0.0"
    url = "www.helse-bergen.no"

    def __init__(self):
        super(PDFPlugin, self).__init__(self.name, self.description,
                                       self.authors, self.version, self.url)

    def _read_image(self, f, opts, hdr):
        """Read image data from given file handle

        Args:
            self: format plugin instance
            f: file handle or filename (depending on self._need_local_file)
            opts: Input options (dict)
            hdr: Header
        Returns:
            Tuple of
                hdr: Header
                    Return values:
                        - info: Internal data for the plugin
                            None if the given file should not be included (e.g. raw file)
                si: numpy array (multi-dimensional)
        """

        self.dpi = 150  # dpi
        self.rotate = 0
        self.encapsulate = 'false'
        self.documentTitle = self.manufacturer = ''
        self.acqdatetime = '19700101'
        legal_attributes = {'dpi', 'rotate', 'encapsulate'}
        if 'input_options' in opts and opts['input_options']:
            for attr in opts['input_options']:
                if attr in legal_attributes:
                    setattr(self, attr, opts['input_options'][attr])
                else:
                    raise ValueError('Unknown attribute {} set in input_options'.format(attr))
        self.dpi = int(self.dpi)
        self.rotate = int(self.rotate)
        if isinstance(self.encapsulate, str):
            self.encapsulate = self.encapsulate.lower() in ['true', 'on']
        if self.rotate not in {0, 90}:
            raise ValueError('psopt rotate value {} is not implemented'.format(self.rotate))

        if hdr.input_order == 'auto':
            hdr.input_order = 'none'

        if self.encapsulate:
            self.EncapsulatedDocument = self.generate_pdf_document(f)
            si = None
            return hdr, si

        # No PDF encapsulation, convert PDF to bitmaps
        image_list = []
        try:
            # Convert filename to bitmap
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(f)
            # version = pdf.get_version()  # get the PDF standard version
            self.documentTitle = pdf.get_metadata_value('Title')
            self.manufacturer = pdf.get_metadata_value('Creator')
            self.acqdatetime = pdf.get_metadata_value('CreationDate').split('+')[0]
            if self.acqdatetime[:2] == 'D:':
                self.acqdatetime = self.acqdatetime[2:]
            n_pages = len(pdf)  # get the number of pages in the document
            for i in range(n_pages):
                page = pdf[i]
                bitmap = page.render(
                    scale=self.dpi/72,  # 72dpi resolution
                    rotation=self.rotate,  # no additional rotation
                    # ... further rendering options
                )
                im = bitmap.to_numpy()
                image_list.append(im)
        except Exception as e:
            raise imagedata.formats.NotImageError('{} does not look like a PDF file ({})'.format(f, e))
        if len(image_list) < 1:
            raise ValueError('No image data read')
        max_rows = max([img.shape[0] for img in image_list])
        max_columns = max([img.shape[1] for img in image_list])
        shape = (len(image_list), max_rows, max_columns)
        dtype = np.dtype([('R', 'u1'), ('G', 'u1'), ('B', 'u1')])
        si = np.zeros(shape, dtype)
        for i, img in enumerate(image_list):
            logger.debug('read: img {} si {}'.format(img.size, si.size))
            si[i, :img.shape[0], :img.shape[1]]['R'] = img[..., 0]
            si[i, :img.shape[0], :img.shape[1]]['G'] = img[..., 1]
            si[i, :img.shape[0], :img.shape[1]]['B'] = img[..., 2]
        hdr.spacing = (1.0, 1.0, 1.0)
        # Color space: RGB
        hdr.photometricInterpretation = 'RGB'
        hdr.color = True
        if self.rotate == 90:
            si = np.rot90(si, axes=(1,2))
        # Let a single page be a 2D image
        if si.ndim == 3 and si.shape[0] == 1:
            si.shape = si.shape[1:]
        logger.debug('read: si {}'.format(si.shape))
        return True, si

    def _need_local_file(self):
        """Do the plugin need access to local files?

        Returns:
            Boolean
                - True: The plugin need access to local filenames
                - False: The plugin can access files given by an open file handle
        """

        return False

    def _set_tags(self, image_list, hdr, si):
        """Set header tags.

        Args:
            self: format plugin instance
            image_list: list with (info,img) tuples
            hdr: Header
            si: numpy array (multi-dimensional)
        Returns:
            hdr: Header
        """

        hdr.dicomToDo.append((pydicom.datadict.tag_for_keyword('Modality'), 'DOC', None, None))
        hdr.dicomToDo.append((pydicom.datadict.tag_for_keyword('ConversionType'), 'WSD', None, None))
        hdr.dicomToDo.append((pydicom.datadict.tag_for_keyword('BurnedInAnnotation'), 'YES', None, None))
        hdr.dicomToDo.append((pydicom.datadict.tag_for_keyword('RecognizableVisualFeatures'), 'YES', None, None))
        hdr.dicomToDo.append((pydicom.datadict.tag_for_keyword('DocumentTitle'), self.documentTitle, None, None))
        hdr.dicomToDo.append((pydicom.datadict.tag_for_keyword('VerificationFlag'), 'UNVERIFIED', None, None))
        hdr.dicomToDo.append((pydicom.datadict.tag_for_keyword('AcquisitionDateTime'), self.acqdatetime, None, None))
        hdr.dicomToDo.append((pydicom.datadict.tag_for_keyword('Manufacturer'), self.manufacturer, None, None))

        if self.encapsulate:
            hdr.SOPClassUID = UID('1.2.840.10008.5.1.4.1.1.104.1')
            hdr.dicomToDo.append((
                pydicom.datadict.tag_for_keyword('EncapsulatedDocument'),
                self.EncapsulatedDocument, None, None
            ))
            hdr.dicomToDo.append((
                pydicom.datadict.tag_for_keyword('MIMETypeOfEncapsulatedDocument'),
                'application/pdf', None, None
            ))
            return

        # Default spacing and orientation
        hdr.spacing = (1.0, 1.0, 1.0)
        hdr.imagePositions = {}
        hdr.imagePositions[0] = np.array([0,0,0])
        hdr.orientation = np.array([0,1,0,-1,0,0])

        # Set tags
        axes = list()
        nz = 1
        axes.append(imagedata.axis.UniformLengthAxis(
            'row',
            hdr.imagePositions[0][1],
            si.shape[-2],
            hdr.spacing[1])
        )
        axes.append(imagedata.axis.UniformLengthAxis(
            'column',
            hdr.imagePositions[0][2],
            si.shape[-1],
            hdr.spacing[2])
        )
        if si.ndim > 2:
            nz = si.shape[-3]
            axes.insert(0, imagedata.axis.UniformLengthAxis(
                'slice',
                hdr.imagePositions[0][0],
                nz,
                hdr.spacing[0])
            )
        hdr.axes = axes

        tags = {}
        for slice in range(nz):
            tags[slice] = np.array([0])
        hdr.tags = tags

        return

    def generate_pdf_document(self, f):
        f_read = f.read()
        # All Dicom Elements must have an even ValueLength
        if len(f_read) % 2 != 0:
            f_read += b'\0'
        return f_read

    def write_3d_numpy(self, si, destination, opts):
        """Write 3D numpy image as PostScript file

        Args:
            self: ITKPlugin instance
            si: Series array (3D or 4D), including these attributes:
            - slices,
            - spacing,
            - imagePositions,
            - transformationMatrix,
            - orientation,
            - tags

            destination: dict of archive and filenames
            opts: Output options (dict)
        Raises:
            imagedata.formats.WriteNotImplemented: Always, writing is not implemented.
        """
        raise imagedata.formats.WriteNotImplemented(
            'Writing PDF files is not implemented.')

    def write_4d_numpy(self, si, destination, opts):
        """Write 4D numpy image as PostScript files

        Args:
            self: ITKPlugin instance
            si[tag,slice,rows,columns]: Series array, including these attributes:
            - slices,
            - spacing,
            - imagePositions,
            - transformationMatrix,
            - orientation,
            - tags

            destination: dict of archive and filenames
            opts: Output options (dict)
        Raises:
            imagedata.formats.WriteNotImplemented: Always, writing is not implemented.
        """
        raise imagedata.formats.WriteNotImplemented(
            'Writing PDF files is not implemented.')
