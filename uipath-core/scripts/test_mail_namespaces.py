"""Regression tests: mail workflows must be well-formed XML.

Bug: gen_send_mail / gen_get_imap_mail emit Integration-Service BackupSlot
subtrees using the usau:/umame:/umae:/p: prefixes, and MailMessage variables
map to snm: — but the root <Activity> never declared them, so every
mail-containing workflow failed XML parsing (and would be rejected by
namespace-strict XAML deserializers such as UiPath Studio's).

Found by aria-modeler Phase 5.5 QA (2026-07-13, PHASE5.5_generation_modes.md
BUG-2); fixed via the has_mail flag in _build_namespaces (same pattern as
has_http).
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_workflow import generate_workflow  # noqa: E402


def _spec(activities, variables=None):
    return {
        "class_name": "MailNamespaceRegression",
        "arguments": [],
        "variables": variables or [],
        "activities": activities,
    }


def test_send_mail_workflow_is_well_formed_xml():
    xaml = generate_workflow(_spec([
        {"gen": "send_mail", "args": {
            "to_variable": "strTo",
            "subject_variable": "strSubject",
            "body_variable": "strBody",
        }},
    ], variables=[
        {"name": "strTo", "type": "String"},
        {"name": "strSubject", "type": "String"},
        {"name": "strBody", "type": "String"},
    ]))
    ET.fromstring(xaml)  # raises ParseError on undeclared prefixes
    for prefix in ("xmlns:usau=", "xmlns:umame=", "xmlns:umae=", "xmlns:p="):
        assert prefix in xaml, f"missing {prefix} declaration"


def test_get_imap_workflow_is_well_formed_xml():
    xaml = generate_workflow(_spec([
        {"gen": "get_imap_mail", "args": {
            "messages_variable": "lstMessages",
        }},
    ], variables=[
        {"name": "lstMessages", "type": "List(MailMessage)"},
    ]))
    ET.fromstring(xaml)
    assert "xmlns:snm=" in xaml
    assert "xmlns:usau=" in xaml


def test_mailmessage_variable_alone_triggers_snm_declaration():
    # save_mail_attachments emits only ui: elements, but its flows carry
    # snm:MailMessage-typed variables — the type alone must trigger the block.
    xaml = generate_workflow(_spec([
        {"gen": "save_mail_attachments", "args": {
            "message_variable": "mail",
            "folder_path_variable": "strFolder",
        }},
    ], variables=[
        {"name": "mail", "type": "MailMessage"},
        {"name": "strFolder", "type": "String"},
    ]))
    ET.fromstring(xaml)
    assert "xmlns:snm=" in xaml


def test_non_mail_workflow_does_not_get_mail_namespaces():
    xaml = generate_workflow(_spec([
        {"gen": "log_message", "args": {"message": "hello"}},
    ]))
    ET.fromstring(xaml)
    assert "xmlns:usau=" not in xaml
    assert "xmlns:snm=" not in xaml
