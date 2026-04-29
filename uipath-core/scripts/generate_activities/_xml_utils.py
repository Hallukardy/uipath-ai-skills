"""XML building blocks for activity generators — selectors, viewstate, OCR, target app, and body blocks.

Extracted from generate_activities.py. These functions produce reusable XAML
fragments consumed by the individual activity generator modules.
"""

import re

from ._helpers import _uuid, _selector_uuid, _escape_xml_attr, _normalize_selector_quotes, _hs


_RE_SEQUENCE_OPEN = re.compile(r"<Sequence(?=[\s/>])[^>]*>")
_RE_SEQUENCE_CLOSE = re.compile(r"</Sequence>")


def extract_sequence_body(xaml: str) -> str:
    """Return the inner content of the OUTERMOST `<Sequence>` in a workflow XAML.

    For workflows produced by `generate_workflow.generate_workflow()`, this
    strips the `<Activity>`/`<x:Members>`/outer `<Sequence>` envelope and
    returns just the activity list — ready to inject into a framework
    file's existing `<Sequence>` via `modify_framework.replace-marker` or
    `insert-invoke`.

    Uses a depth-counted scan over the raw text instead of an XML parser
    so attribute order, whitespace, and inline comments survive intact —
    `ElementTree`'s round-trip would normalize them. The regex requires a
    whitespace, `/`, or `>` immediately after `Sequence` so property tags
    like `<Sequence.Variables>` aren't mistaken for nested elements
    (otherwise the depth counter never balances).

    Raises ValueError if no balanced `<Sequence>` is found.
    """
    m = _RE_SEQUENCE_OPEN.search(xaml)
    if not m:
        raise ValueError("No <Sequence> found in XAML")
    start = m.end()
    depth = 1
    i = start
    while depth > 0:
        m_close = _RE_SEQUENCE_CLOSE.search(xaml, i)
        if m_close is None:
            raise ValueError("Unbalanced <Sequence> tags in XAML")
        m_open = _RE_SEQUENCE_OPEN.search(xaml, i)
        if m_open is not None and m_open.start() < m_close.start():
            depth += 1
            i = m_open.end()
        else:
            depth -= 1
            if depth == 0:
                return xaml[start:m_close.start()].strip()
            i = m_close.end()
    raise ValueError("Unbalanced <Sequence> tags in XAML")


def strip_leading_viewstate(body: str) -> str:
    """Drop a leading `<sap:WorkflowViewStateService.ViewState>...</...>` block.

    Snippets bound for `modify_framework.replace-marker` / `insert-invoke`
    must NOT carry their own ViewState dictionary — the destination
    `<Sequence>` already owns one, and Studio rejects duplicates with
    `XamlDuplicateMemberException` at load time. Idempotent when no
    leading block is present.
    """
    if not re.match(r"\s*<sap:WorkflowViewStateService\.ViewState>", body):
        return body
    end_tag = "</sap:WorkflowViewStateService.ViewState>"
    end = body.find(end_tag)
    if end == -1:
        return body
    return body[end + len(end_tag):].lstrip()


def _selector_xml(selector: str, obj_repo: dict = None) -> str:
    """Generate TargetAnchorable XML element.

    Args:
        selector: Raw UiPath selector string.
        obj_repo: Optional Object Repository reference dict with keys:
            - reference: "LibraryId/ElementId" (from generate_object_repository)
            - content_hash: ContentHash string
            - guid: Fixed GUID (must match Object Repository entry)
    """
    selector = _normalize_selector_quotes(selector)
    escaped = _escape_xml_attr(selector)
    guid = obj_repo["guid"] if obj_repo else _selector_uuid(selector)
    extra_attrs = ""
    if obj_repo:
        ch = obj_repo.get("content_hash", "")
        ref = obj_repo.get("reference", "")
        if ch:
            extra_attrs += f' ContentHash="{ch}"'
        if ref:
            extra_attrs += f' Reference="{ref}"'
    return f'<uix:TargetAnchorable{extra_attrs} ElementVisibilityArgument="Interactive" FullSelectorArgument="{escaped}" Guid="{guid}" SearchSteps="Selector" Version="V6" WaitForReadyArgument="Interactive" />'


def _viewstate_block(id_ref: str, is_expanded: bool = True) -> str:
    lines = ['<sap:WorkflowViewStateService.ViewState>',
             '  <scg:Dictionary x:TypeArguments="x:String, x:Object">',
             f'    <x:Boolean x:Key="IsExpanded">{str(is_expanded)}</x:Boolean>',
             '  </scg:Dictionary>', '</sap:WorkflowViewStateService.ViewState>']
    return "\n".join(lines)


def _ocr_engine_block(i2, i3, i4, i5):
    return f"""{i2}<uix:NApplicationCard.OCREngine>
{i3}<ActivityFunc x:TypeArguments="sd:Image, scg:IEnumerable(scg:KeyValuePair(sd1:Rectangle, x:String))">
{i4}<ActivityFunc.Argument>
{i5}<DelegateInArgument x:TypeArguments="sd:Image" Name="Image" />
{i4}</ActivityFunc.Argument>
{i3}</ActivityFunc>
{i2}</uix:NApplicationCard.OCREngine>"""


def _target_app_empty(i2, i3, i4, i5):
    return f"""{i2}<uix:NApplicationCard.TargetApp>
{i3}<uix:TargetApp Area="0, 0, 0, 0">
{i4}<uix:TargetApp.Arguments>
{i5}<InArgument x:TypeArguments="x:String" />
{i4}</uix:TargetApp.Arguments>
{i4}<uix:TargetApp.FilePath>
{i5}<InArgument x:TypeArguments="x:String" />
{i4}</uix:TargetApp.FilePath>
{i4}<uix:TargetApp.WorkingDirectory>
{i5}<InArgument x:TypeArguments="x:String" />
{i4}</uix:TargetApp.WorkingDirectory>
{i3}</uix:TargetApp>
{i2}</uix:NApplicationCard.TargetApp>"""


def _target_app_with_selector(selector, i2, i3, i4, i5):
    """TargetApp block with a window selector for desktop attach/close."""
    sel = _normalize_selector_quotes(selector)
    esc_sel = _escape_xml_attr(sel)
    return f"""{i2}<uix:NApplicationCard.TargetApp>
{i3}<uix:TargetApp Area="0, 0, 0, 0" Selector="{esc_sel}">
{i4}<uix:TargetApp.Arguments>
{i5}<InArgument x:TypeArguments="x:String" />
{i4}</uix:TargetApp.Arguments>
{i4}<uix:TargetApp.FilePath>
{i5}<InArgument x:TypeArguments="x:String" />
{i4}</uix:TargetApp.FilePath>
{i4}<uix:TargetApp.WorkingDirectory>
{i5}<InArgument x:TypeArguments="x:String" />
{i4}</uix:TargetApp.WorkingDirectory>
{i3}</uix:TargetApp>
{i2}</uix:NApplicationCard.TargetApp>"""


def _body_block(body_content, body_seq_idref, i2, i3, i4, i5):
    # NOTE: Do NOT add _viewstate_block here. The body_content passed by the caller
    # already contains its own ViewState block. Adding one here causes
    # XamlDuplicateMemberException: 'ViewState' property has already been set on 'Sequence'.
    return f"""{i2}<uix:NApplicationCard.Body>
{i3}<ActivityAction x:TypeArguments="x:Object">
{i4}<ActivityAction.Argument>
{i5}<DelegateInArgument x:TypeArguments="x:Object" Name="WSSessionData" />
{i4}</ActivityAction.Argument>
{i4}<Sequence DisplayName="Do" sap2010:WorkflowViewState.IdRef="{body_seq_idref}">
{body_content}
{i4}</Sequence>
{i3}</ActivityAction>
{i2}</uix:NApplicationCard.Body>"""
