from . import analysis_commands as analysis
from . import fw_commands as fw
from . import reader_commands as reader

command_analyze = analysis.command_analyze
command_capture = analysis.command_capture
command_interactive = analysis.command_interactive
command_prepare_reader = reader.command_prepare_reader
command_reader_info = reader.command_reader_info
command_test_medium = reader.command_test_medium
command_update_reader = reader.command_update_reader
command_export_fw = fw.command_export_fw
