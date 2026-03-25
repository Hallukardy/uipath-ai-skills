"""generate_activities package -- re-exports all 94 gen_* functions.

Preserves the import contract: from generate_activities import gen_ntypeinto
"""

from .application_card import (  # noqa: F401
    gen_napplicationcard_attach,
    gen_napplicationcard_close,
    gen_napplicationcard_desktop_open,
    gen_napplicationcard_open,
)

from .control_flow import (  # noqa: F401
    gen_do_while,
    gen_flowchart,
    gen_foreach,
    gen_foreach_file,
    gen_foreach_row,
    gen_if,
    gen_if_else_if,
    gen_parallel,
    gen_parallel_foreach,
    gen_state_machine,
    gen_switch,
    gen_while,
)

from .data_operations import (  # noqa: F401
    gen_add_data_column,
    gen_add_data_row,
    gen_assign,
    gen_build_data_table,
    gen_filter_data_table,
    gen_generate_data_table,
    gen_join_data_tables,
    gen_lookup_data_table,
    gen_merge_data_table,
    gen_multiple_assign,
    gen_output_data_table,
    gen_remove_data_column,
    gen_remove_duplicate_rows,
    gen_sort_data_table,
    gen_variables_block,
)

from .dialogs import (  # noqa: F401
    gen_input_dialog,
    gen_message_box,
)

from .error_handling import (  # noqa: F401
    gen_rethrow,
    gen_retryscope,
    gen_throw,
    gen_try_catch,
)

from .file_system import (  # noqa: F401
    gen_copy_file,
    gen_create_directory,
    gen_delete_file,
    gen_move_file,
    gen_path_exists,
    gen_read_csv,
    gen_read_text_file,
    gen_write_csv,
    gen_write_text_file,
)

from .http_json import (  # noqa: F401
    gen_deserialize_json,
    gen_net_http_request,
)

from .integrations import (  # noqa: F401
    gen_append_range,
    gen_database_connect,
    gen_execute_non_query,
    gen_execute_query,
    gen_get_imap_mail,
    gen_read_pdf_text,
    gen_read_pdf_with_ocr,
    gen_read_range,
    gen_save_mail_attachments,
    gen_send_mail,
    gen_write_cell,
    gen_write_range,
)

from .invoke import (  # noqa: F401
    gen_invoke_code,
    gen_invoke_method,
    gen_invoke_workflow,
)

from .logging_misc import (  # noqa: F401
    gen_add_log_fields,
    gen_break,
    gen_comment,
    gen_comment_out,
    gen_continue,
    gen_kill_process,
    gen_logmessage,
    gen_remove_log_fields,
    gen_should_stop,
    gen_take_screenshot_and_save,
    gen_terminate_workflow,
)

from .navigation import (  # noqa: F401
    gen_nextractdata,
    gen_ngeturl,
    gen_ngotourl,
    gen_pick_login_validation,
)

from .orchestrator import (  # noqa: F401
    gen_add_queue_item,
    gen_bulk_add_queue_items,
    gen_get_queue_item,
    gen_get_robot_asset,
    gen_getrobotcredential,
)

from .ui_automation import (  # noqa: F401
    gen_ncheck,
    gen_ncheckstate,
    gen_nclick,
    gen_ndoubleclick,
    gen_ngettext,
    gen_nhover,
    gen_nkeyboardshortcuts,
    gen_nmousescroll,
    gen_nrightclick,
    gen_nselectitem,
    gen_ntypeinto,
)


__all__ = [
    "gen_add_data_column",
    "gen_add_data_row",
    "gen_add_log_fields",
    "gen_add_queue_item",
    "gen_append_range",
    "gen_assign",
    "gen_break",
    "gen_build_data_table",
    "gen_bulk_add_queue_items",
    "gen_comment",
    "gen_comment_out",
    "gen_continue",
    "gen_copy_file",
    "gen_create_directory",
    "gen_database_connect",
    "gen_delete_file",
    "gen_deserialize_json",
    "gen_do_while",
    "gen_execute_non_query",
    "gen_execute_query",
    "gen_filter_data_table",
    "gen_flowchart",
    "gen_foreach",
    "gen_foreach_file",
    "gen_foreach_row",
    "gen_generate_data_table",
    "gen_get_imap_mail",
    "gen_get_queue_item",
    "gen_get_robot_asset",
    "gen_getrobotcredential",
    "gen_if",
    "gen_if_else_if",
    "gen_input_dialog",
    "gen_invoke_code",
    "gen_invoke_method",
    "gen_invoke_workflow",
    "gen_join_data_tables",
    "gen_kill_process",
    "gen_logmessage",
    "gen_lookup_data_table",
    "gen_merge_data_table",
    "gen_message_box",
    "gen_move_file",
    "gen_multiple_assign",
    "gen_napplicationcard_attach",
    "gen_napplicationcard_close",
    "gen_napplicationcard_desktop_open",
    "gen_napplicationcard_open",
    "gen_ncheck",
    "gen_ncheckstate",
    "gen_nclick",
    "gen_ndoubleclick",
    "gen_net_http_request",
    "gen_nextractdata",
    "gen_ngettext",
    "gen_ngeturl",
    "gen_ngotourl",
    "gen_nhover",
    "gen_nkeyboardshortcuts",
    "gen_nmousescroll",
    "gen_nrightclick",
    "gen_nselectitem",
    "gen_ntypeinto",
    "gen_output_data_table",
    "gen_parallel",
    "gen_parallel_foreach",
    "gen_path_exists",
    "gen_pick_login_validation",
    "gen_read_csv",
    "gen_read_pdf_text",
    "gen_read_pdf_with_ocr",
    "gen_read_range",
    "gen_read_text_file",
    "gen_remove_data_column",
    "gen_remove_duplicate_rows",
    "gen_remove_log_fields",
    "gen_rethrow",
    "gen_retryscope",
    "gen_save_mail_attachments",
    "gen_send_mail",
    "gen_should_stop",
    "gen_sort_data_table",
    "gen_state_machine",
    "gen_switch",
    "gen_take_screenshot_and_save",
    "gen_terminate_workflow",
    "gen_throw",
    "gen_try_catch",
    "gen_variables_block",
    "gen_while",
    "gen_write_cell",
    "gen_write_csv",
    "gen_write_range",
    "gen_write_text_file",
]

# Core generators that require uix: namespace (UI automation activities).
# Single source of truth — consumed by generate_workflow.py for namespace detection.
UI_GENERATORS = frozenset({
    "ntypeinto", "nclick", "ncheck", "nhover", "ndoubleclick", "nrightclick",
    "ngettext", "ncheckstate", "nselectitem", "nkeyboardshortcuts",
    "nmousescroll", "ngotourl", "nextractdata", "ngeturl",
    "napplicationcard_open", "napplicationcard_attach",
    "napplicationcard_close", "napplicationcard_desktop_open",
    "pick_login_validation",
})

