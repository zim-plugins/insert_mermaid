from zim.plugins import PluginClass
from zim.plugins.base.imagegenerator import \
    ImageGeneratorClass, BackwardImageGeneratorObjectType

from zim.fs import File, TmpFile
from zim.applications import Application, ApplicationError

import json

import logging

import os

logger = logging.getLogger('zim.plugins.insert_mermaid')
# https://github.com/mermaidjs/mermaid.cli#options
puppeteer_config = os.path.dirname(os.path.abspath(__file__)) + "/data/puppeteer-config.json"
mmdc_cmd = ['mmdc', "-p", puppeteer_config]
convert_cmd = ['convert']


class InsertMermaidPlugin(PluginClass):
    plugin_info = {
        'name': 'Insert Image from Mermaid',  # T: plugin name
        'description': 'This plugin provides a mermaid editor for zim based on Mermaid.',  # T: plugin description
        'help': 'README.md',
        'author': 'k4nzdroid@163.com',
    }

    @classmethod
    def check_dependencies(klass):
        has_mmdc_cmd = Application(mmdc_cmd).tryexec()
        has_convert_cmd = Application(convert_cmd).tryexec()
        return (has_mmdc_cmd and has_convert_cmd), [("mmdc", has_mmdc_cmd, True), ("convert", has_convert_cmd, True)]


class BackwardMermaidImageObjectType(BackwardImageGeneratorObjectType):
    name = 'image+mermaid'
    label = 'Image from Mermaid'  # T: menu item
    syntax = 'mmd'
    scriptname = 'mermaid.mmd'
    imagefile_extension = '.png'


class MermaidGenerator(ImageGeneratorClass):

    def __init__(self, plugin, notebook, page):
        ImageGeneratorClass.__init__(self, plugin, notebook, page)
        self.mmd_file = TmpFile('mermaid.mmd')
        self.mmd_file.touch()
        self.png_file = File(self.mmd_file.path[:-4] + '.png')  # len('.dot') == 4

    def generate_image(self, text):

        # Write to tmp file
        self.mmd_file.write(text)

        # Call mmdc
        try:
            mmdc = Application(mmdc_cmd)
            mmdc.run(("-i", self.mmd_file, "-o", self.png_file))
        except ApplicationError:
            logger.exception("[PLUGIN:INSERT MERMAID] ApplicationError: mmdc error.")
            return None, None
        else:
            if not self.png_file.exists():
                logger.exception("[PLUGIN:INSERT MERMAID] png file not exists: ")
                return None, None

        # Call convert
        # If the first line is a comment and the content is a JSON string, Parse it as convert options.
        # This is a workaround used to control image size, Cause the language doesn't support image size control.
        # !!! The following code is quite stupid but works.
        try:
            assert len(text.partition('\n')) > 0
            first_line = text.partition('\n')[0]

            assert first_line.startswith("%% ")
            assert json.loads(first_line.replace("%% ", "", 1))
            cmd_opts = json.loads(first_line.replace("%% ", "", 1))

            assert "width" in cmd_opts
            assert "height" in cmd_opts
            image_width = cmd_opts['width']
            image_height = cmd_opts['height']

            assert int(image_width) > 0 and int(image_height) > 0
            convert = Application(convert_cmd)
            convert.run((self.png_file, "-resize", image_width + "x" + image_height, self.png_file))

            return self.png_file, None
        except ApplicationError:
            logger.error("[PLUGIN:INSERT MERMAID] Application Error.")
            return None, None  # covert error. The original png file is corrupted.
        except Exception as e:
            logger.error("[PLUGIN:INSERT MERMAID] convert error: %s" % str(e))
            return self.png_file, None  # return the original png file

    def cleanup(self):
        self.mmd_file.remove()
        self.png_file.remove()
