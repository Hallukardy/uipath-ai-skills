"""Error handling activity generators."""
from ._helpers import _hs, _uuid, _escape_xml_attr, _escape_vb_expr
from ._xml_utils import _viewstate_block


def gen_try_catch(try_content, try_sequence_idref, id_ref,
                  catches=None, finally_content="", finally_sequence_idref="",
                  display_name="Try Catch", indent="    "):
    """Generate TryCatch — structured error handling.

    Hallucination patterns prevented:
    - Missing ActivityAction wrapper in Catch blocks
    - Missing DelegateInArgument declaration
    - Wrong exception TypeArguments
    - Missing Catches collection wrapper (<TryCatch.Catches>)

    Args:
        try_content: XAML string for Try body (pre-indented)
        try_sequence_idref: IdRef for Try's Sequence
        id_ref: Base IdRef number
        catches: List of (exception_type, variable_name, catch_content, catch_sequence_idref) tuples.
                 exception_type: "s:Exception", "ui:BusinessRuleException", etc.
                 e.g. [("ui:BusinessRuleException", "breException", "...", "Seq_CatchBRE_1"),
                       ("s:Exception", "exception", "...", "Seq_CatchEx_1")]
                 Order matters: specific exceptions FIRST, generic Exception LAST.
                 If None, creates single generic Exception catch.
        finally_content: XAML string for Finally body (optional)
        finally_sequence_idref: IdRef for Finally's Sequence
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5, i6, i7 = (indent, indent+"  ", indent+"    ",
                                   indent+"      ", indent+"        ",
                                   indent+"          ", indent+"            ")

    # Default catch: generic Exception
    if catches is None:
        catches = [("s:Exception", "exception", "", f"Sequence_CatchEx_{id_ref}")]

    # Try block
    try_block = f"""{i2}<TryCatch.Try>
{i3}<Sequence DisplayName="Try" sap2010:WorkflowViewState.IdRef="{try_sequence_idref}">
{i4}{_viewstate_block(try_sequence_idref)}
{try_content}
{i3}</Sequence>
{i2}</TryCatch.Try>"""

    # Catches
    catch_blocks = []
    for exc_type, var_name, catch_body, catch_seq_id in catches:
        catch_blocks.append(f"""{i3}<Catch x:TypeArguments="{exc_type}">
{i4}<ActivityAction x:TypeArguments="{exc_type}">
{i5}<ActivityAction.Argument>
{i6}<DelegateInArgument x:TypeArguments="{exc_type}" Name="{var_name}" />
{i5}</ActivityAction.Argument>
{i5}<Sequence DisplayName="Catch" sap2010:WorkflowViewState.IdRef="{catch_seq_id}">
{i6}{_viewstate_block(catch_seq_id)}
{catch_body}
{i5}</Sequence>
{i4}</ActivityAction>
{i3}</Catch>""")

    catches_xml = "\n".join(catch_blocks)
    catches_block = f"""{i2}<TryCatch.Catches>
{catches_xml}
{i2}</TryCatch.Catches>"""

    # Finally (optional)
    finally_block = ""
    if finally_content and finally_sequence_idref:
        finally_block = f"""
{i2}<TryCatch.Finally>
{i3}<Sequence DisplayName="Finally" sap2010:WorkflowViewState.IdRef="{finally_sequence_idref}">
{i4}{_viewstate_block(finally_sequence_idref)}
{finally_content}
{i3}</Sequence>
{i2}</TryCatch.Finally>"""

    return f"""{i}<TryCatch DisplayName="{dn}" {_hs("TryCatch")} sap2010:WorkflowViewState.IdRef="TryCatch_{id_ref}">
{try_block}
{catches_block}{finally_block}
{i}</TryCatch>"""


def gen_throw(exception_expression, id_ref, display_name="Throw", indent="            "):
    hs = _hs("Throw")
    dn = _escape_xml_attr(display_name)
    esc_expr = _escape_vb_expr(exception_expression)
    i = indent
    return f'{i}<Throw DisplayName="{dn}" Exception="[{esc_expr}]" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" />'


def gen_rethrow(id_ref, display_name="Rethrow", indent="    "):
    """Generate Rethrow — re-raises current exception preserving stack trace."""
    dn = _escape_xml_attr(display_name)
    i = indent
    return f'{i}<Rethrow DisplayName="{dn}" sap2010:WorkflowViewState.IdRef="Rethrow_{id_ref}" />'


def gen_retryscope(display_name, id_ref, body_content, body_sequence_idref,
                   number_of_retries=3, indent="    "):
    hs = _hs("RetryScope")
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5 = indent, indent+"  ", indent+"    ", indent+"      ", indent+"        "
    return f"""{i}<ui:RetryScope LogRetriedExceptions="{{x:Null}}" RetriedExceptionsLogLevel="{{x:Null}}" DisplayName="{dn}" {hs} NumberOfRetries="{number_of_retries}" sap2010:WorkflowViewState.IdRef="{id_ref}">
{i2}<ui:RetryScope.ActivityBody>
{i3}<ActivityAction>
{i4}<Sequence DisplayName="Action" sap2010:WorkflowViewState.IdRef="{body_sequence_idref}">
{i5}{_viewstate_block(body_sequence_idref)}
{body_content}
{i4}</Sequence>
{i3}</ActivityAction>
{i2}</ui:RetryScope.ActivityBody>
{i2}<ui:RetryScope.Condition>
{i3}<ActivityFunc x:TypeArguments="x:Boolean" />
{i2}</ui:RetryScope.Condition>
{i}</ui:RetryScope>"""
