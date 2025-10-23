#!/usr/bin/env python3

import unittest
import sys
import os.path
import tempfile
import numpy as np
import argparse

from .context import imagedata_format_pdf
import imagedata.cmdline
import imagedata.readdata
import imagedata.formats
from imagedata.series import Series
# from .compare_headers import compare_headers

from imagedata import plugins
sys.path.append(os.path.abspath('src'))
from imagedata_format_pdf.pdfplugin import PDFPlugin
plugin_type = 'format'
plugin_name = PDFPlugin.name + 'format'
class_name = PDFPlugin.name
pclass = PDFPlugin
plugins[plugin_type].append((plugin_name, class_name, pclass))


class Test2DPDFPlugin(unittest.TestCase):
    def setUp(self):
        parser = argparse.ArgumentParser()
        imagedata.cmdline.add_argparse_options(parser)

        self.opts = parser.parse_args(['--serdes', '1'])
        self.encapsulate_opts = parser.parse_args(['--serdes', '1', '--input_options', 'encapsulate=True'])

        plugins = imagedata.formats.get_plugins_list()
        self.pdf_plugin = None
        for pname, ptype, pclass in plugins:
            if ptype == 'pdf':
                self.pdf_plugin = pclass
        self.assertIsNotNone(self.pdf_plugin)
        self.dtype = np.dtype([('R', 'u1'), ('G', 'u1'), ('B', 'u1')])

    # @unittest.skip("skipping test_read_single_file")
    def test_read_single_file(self):
        si1 = Series(
            os.path.join('data', 'pages', 'A_Lovers_Complaint_1.pdf'),
            'none',
            self.opts)
        self.assertEqual(si1.dtype, self.dtype)
        self.assertEqual(si1.shape, (1755, 1240))

    # @unittest.skip("skipping test_read_two_files")
    def test_read_two_files(self):
        si1 = Series(
            [
                os.path.join('data', 'pages', 'A_Lovers_Complaint_1.pdf'),
                os.path.join('data', 'pages', 'A_Lovers_Complaint_2.pdf')
            ],
            'none',
            self.opts)
        self.assertEqual(si1.dtype, self.dtype)
        self.assertEqual(si1.shape, (2, 1755, 1240))

    # @unittest.skip("skipping test_read_single_directory")
    def test_read_single_directory(self):
        si1 = Series(
            os.path.join('data', 'pages'),
            'none',
            self.opts)
        self.assertEqual(si1.dtype, self.dtype)
        self.assertEqual(si1.shape, (6, 1755, 1240))
        # for axis in si1.axes:
        #    logging.debug('test_read_single_directory: axis {}'.format(axis))

    # @unittest.skip("skipping test_read_large_file")
    def test_read_large_file(self):
        si1 = Series(
            os.path.join('data', 'A_Lovers_Complaint.pdf'),
            'none',
            self.opts)
        self.assertEqual(si1.dtype, self.dtype)
        self.assertEqual(si1.shape, (6, 1755, 1240))

    # @unittest.skip("skipping test_zipread_single_file")
    def test_zipread_single_file(self):
        si1 = Series(
            os.path.join('data', 'pages.zip?pages/A_Lovers_Complaint_1.pdf'),
            'none',
            self.opts)
        self.assertEqual(si1.dtype, self.dtype)
        self.assertEqual(si1.shape, (1755, 1240))

    # @unittest.skip("skipping test_zipread_two_files")
    def test_zipread_two_files(self):
        si1 = Series(
            os.path.join('data', 'pages.zip?pages/A_Lovers_Complaint_[12].pdf'),
            'none',
            self.opts)
        self.assertEqual(si1.dtype, self.dtype)
        self.assertEqual(si1.shape, (2, 1755, 1240))

    # @unittest.skip("skipping test_zipread_a_directory")
    def test_zipread_a_directory(self):
        si1 = Series(
            os.path.join('data', 'pages.zip?pages/'),
            'none',
            self.opts)
        self.assertEqual(si1.dtype, self.dtype)
        self.assertEqual(si1.shape, (6, 1755, 1240))

    # @unittest.skip("skipping test_zipread_all")
    def test_zipread_all(self):
        si1 = Series(
            os.path.join('data', 'pages.zip'),
            'none',
            self.opts)
        self.assertEqual(si1.dtype, self.dtype)
        self.assertEqual(si1.shape, (6, 1755, 1240))

    def test_write_dicom_single_file(self):
        si1 = Series(
            os.path.join('data', 'pages', 'A_Lovers_Complaint_1.pdf'),
            'none',
            self.opts)
        with tempfile.TemporaryDirectory() as d:
            si1.write(d, formats=['dicom'])

    def test_write_dicom_files(self):
        si1 = Series(
            os.path.join('data', 'A_Lovers_Complaint.pdf'),
            'none',
            self.opts)
        with tempfile.TemporaryDirectory() as d:
            si1.write(d, formats=['dicom'])

    # @unittest.skip("skipping test_write_single_file")
    def test_write_single_file(self):
        si1 = Series(
            os.path.join('data', 'pages.zip?pages/A_Lovers_Complaint_1.pdf'),
            'none',
            self.opts)
        with self.assertRaises(imagedata.formats.WriteNotImplemented):
            with tempfile.TemporaryDirectory() as d:
                si1.write(d + '?Image%05d.pdf', formats=['pdf'])

    # @unittest.skip("skipping test_encapsulate_single_file")
    def test_encapsulate_single_file(self):
        si1 = Series(
            os.path.join('data', 'pages/A_Lovers_Complaint_1.pdf'),
            'none',
            self.encapsulate_opts)
        si1.seriesDescription = 'A Lovers Complaint page 1'
        with tempfile.TemporaryDirectory() as d:
            si1.write(d, formats=['dicom'])

    # @unittest.skip("skipping test_encapsulate_files")
    def test_encapsulate_files(self):
        si1 = Series(
            os.path.join('data', 'A_Lovers_Complaint.pdf'),
            'none',
            self.encapsulate_opts)
        si1.seriesDescription = 'A Lovers Complaint'
        with tempfile.TemporaryDirectory() as d:
            si1.write(d, formats=['dicom'])


if __name__ == '__main__':
    unittest.main()
