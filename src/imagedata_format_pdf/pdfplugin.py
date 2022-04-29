"""Read/Write PostScript files
"""

# Copyright (c) 2022 Erling Andersen, Haukeland University Hospital,
# Bergen, Norway

import os.path
import locale
import logging
import magic
import tempfile
import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.sequence import Sequence
import datetime
from pdf2image import convert_from_bytes, convert_from_path

import imagedata.formats
from imagedata.formats.abstractplugin import AbstractPlugin
from . import POPPLER_INSTALLED

logger = logging.getLogger(__name__)


class ImageTypeError(Exception):
    """
    Thrown when trying to load or save an image of unknown type.
    """
    pass


class DependencyError(Exception):
    """
    Thrown when a required module could not be loaded.
    """
    pass


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

        if not POPPLER_INSTALLED:
            raise OSError("Poppler is not installed")
        self.dpi = 150  # dpi
        self.rotate = 0
        legal_attributes = {'dpi', 'rotate', 'encapsulate'}
        if 'pdfopt' in opts and opts['pdfopt']:
            for expr in opts['pdfopt'].split(','):
                attr,value = expr.split('=')
                if attr in legal_attributes:
                    setattr(self, attr, value)
                else:
                    raise ValueError('Unknown attribute {} set in psopt'.format(attr))
        self.dpi = int(self.dpi)
        self.rotate = int(self.rotate)
        self.encapsulate = self.encapsulate.lower() == 'true' or self.encapsulate.lower() == 'on'
        if self.rotate not in {0, 90}:
            raise ValueError('psopt rotate value {} is not implemented'.format(self.rotate))
        if self.encapsulate:
            ds = self.generate_dicom_from_pdf(f)
            hdr.DicomHeaderDict = [[(None, None, ds)]]
            hdr.tags = [0]
            hdr.tags[0] = [0]
            return hdr, None

        # No PDF encapsulation, convert PDF to bitmaps
        try:
            # Convert filename to PNG
            # self._convert_to_png(f, tempdir, "fname%02d.png")
            # self._pdf_to_png(f, os.path.join(tempdir.name, "fname.png"))
            # image_list = convert_from_path(f)
            image_list = convert_from_bytes(f.read())
        except imagedata.formats.NotImageError:
            raise imagedata.formats.NotImageError('{} does not look like a PostScript file'.format(f))
        if len(image_list) < 1:
            raise ValueError('No image data read')
        img = image_list[0]
        shape = (len(image_list), img.height, img.width, 3)
        dtype = np.uint8
        si = np.zeros(shape, dtype)
        for i, img in enumerate(image_list):
            logger.debug('read: img {} si {}'.format(img.size, si.size))
            si[i] = img
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

        #super(PDFPlugin, self)._set_tags(image_list, hdr, si)

        # Default spacing and orientation
        hdr.spacing = (1.0, 1.0, 1.0)
        hdr.imagePositions = {}
        hdr.imagePositions[0] = np.array([0,0,0])
        hdr.orientation = np.array([0,1,0,-1,0,0])

        # Set tags
        axes = list()
        _actual_shape = si.shape
        _color = False
        if hdr.color:
            _actual_shape = si.shape[:-1]
            _color = True
        _actual_ndim = len(_actual_shape)
        nz = 1
        axes.append(imagedata.axis.UniformLengthAxis(
            'row',
            hdr.imagePositions[0][1],
            _actual_shape[-2],
            hdr.spacing[1])
        )
        axes.append(imagedata.axis.UniformLengthAxis(
            'column',
            hdr.imagePositions[0][2],
            _actual_shape[-1],
            hdr.spacing[2])
        )
        if _actual_ndim > 2:
            nz = _actual_shape[-3]
            axes.insert(0, imagedata.axis.UniformLengthAxis(
                'slice',
                hdr.imagePositions[0][0],
                nz,
                hdr.spacing[0])
            )
        if _color:
            axes.append(imagedata.axis.VariableAxis(
                'rgb',
                ['r', 'g', 'b'])
            )
        hdr.axes = axes

        tags = {}
        for slice in range(nz):
            tags[slice] = np.array([0])
        hdr.tags = tags
        return

    @staticmethod
    def _pdf_to_png(inputPath, outputPath):
        # def _convert_to_png(self, filename, tempdir, fname):

        """Convert from pdf to png by using python gfx

        The resolution of the output png can be adjusted in the config file
        under General -> zoom, typical value 150
        The quality of the output png can be adjusted in the config file under
        General -> antiAlise, typical value 5

        :param inputPath: path to a pdf file
        :param outputPath: path to the location where the output png will be
            saved
        """
        """
        Args:
        filename: PostScript file
        tempdir:  Output directory
        fname:    Output filename
        Multi-page PostScript files will be converted to fname-N.png
        """
        print("converting pdf {} {}".format(inputPath, outputPath))
        gfx.setparameter("zoom", config.readConfig("zoom"))  # Gives the image higher resolution
        doc = gfx.open("pdf", inputPath)
        img = gfx.ImageList()

        img.setparameter("antialise", config.readConfig("antiAliasing"))  # turn on antialising
        page1 = doc.getPage(1)
        img.startpage(page1.width, page1.height)
        page1.render(img)
        img.endpage()
        img.save(outputPath)
        
    def generate_dicom_from_pdf(self, f):
        suffix = '.dcm'
        filename = tempfile.NamedTemporaryFile(suffix=suffix).name

        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.104.1'
        file_meta.MediaStorageSOPInstanceUID = '2.16.840.1.114430.287196081618142314176776725491661159509.60.1'
        file_meta.ImplementationClassUID = '1.3.46.670589.50.1.8.0'
        file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'

        ds = FileDataset(filename, {},
                     file_meta=file_meta, preamble=b"\0" * 128)

        ds.is_little_endian = True
        ds.is_implicit_VR = False

        dt = datetime.datetime.now()
        ds.StudyDate = dt.strftime('%Y%m%d')
        ds.StudyTime = dt.strftime('%H%M%S.%f')
        ds.ContentDate = dt.strftime('%Y%m%d')
        ds.ContentTime = dt.strftime('%H%M%S.%f')
        ds.AcquisitionDateTime = '19700101'
        ds.Manufacturer = 'imagedata'
        ds.ReferringPhysicianName = ''

        ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.104.1'

        f_read = f.read()
        ValueLength = len(f_read)
        # All Dicom Element must have an even ValueLength
        if ValueLength % 2 != 0:
            f_read += b'\0'
        ds.EncapsulatedDocument = f_read

        ds.MIMETypeOfEncapsulatedDocument = 'application/pdf'

        ds.Modality = 'DOC'  # document
        ds.ConversionType = 'WSD'  # workstation
        ds.SpecificCharacterSet = 'ISO_IR 100' 
        # more codes for character encoding here https://dicom.innolitics.com/ciods/cr-image/sop-common/00080005
        ds.BurnedInAnnotation = 'YES'
        ds.RecognizableVisualFeatures = 'YES'
        ds.DocumentTitle = ''
        ds.VerificationFlag = 'UNVERIFIED'
        ds.InstanceNumber = 1
        ds.ConceptNameCodeSequence = Sequence([])

        return ds

    def write_3d_numpy(self, si, destination, opts):
        """Write 3D numpy image as PostScript file

        Args:
            self: ITKPlugin instance
            si: Series array (3D or 4D), including these attributes:
            -   slices,
            -   spacing,
            -   imagePositions,
            -   transformationMatrix,
            -   orientation,
            -   tags

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
            -   slices,
            -   spacing,
            -   imagePositions,
            -   transformationMatrix,
            -   orientation,
            -   tags

            destination: dict of archive and filenames
            opts: Output options (dict)
        Raises:
            imagedata.formats.WriteNotImplemented: Always, writing is not implemented.
        """
        raise imagedata.formats.WriteNotImplemented(
            'Writing PDF files is not implemented.')
