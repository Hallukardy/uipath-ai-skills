"""Invoke activity generators."""
from ._helpers import _hs, _uuid, _escape_xml_attr, _escape_vb_expr, _normalize_type_arg
from ._xml_utils import _viewstate_block


def gen_invoke_workflow(workflow_path, display_name, id_ref, arguments=None, indent="    "):
    """Args: arguments = {key: (direction, type, value_expression)}"""
    hs = _hs("InvokeWorkflowFile")
    dn = _escape_xml_attr(display_name)
    wp = _escape_xml_attr(workflow_path)
    i, i2, i3 = indent, indent+"  ", indent+"    "
    if not arguments:
        return f'{i}<ui:InvokeWorkflowFile ArgumentsVariable="{{x:Null}}" DisplayName="{dn}" WorkflowFileName="{wp}" UnSafe="False" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" />'
    # Defensive: accept both dict {key: (dir, type, expr)} and list of tuples.
    # Known list formats from LLM: [(dir, type, expr, key), ...] or [(key, dir, type, expr), ...]
    if isinstance(arguments, list):
        converted = {}
        for item in arguments:
            if len(item) == 4:
                # Heuristic: if item[0] is a direction keyword, format is (dir, type, expr, key)
                if item[0] in ("In", "Out", "InOut"):
                    converted[item[3]] = (item[0], item[1], item[2])
                else:
                    # Format is (key, dir, type, expr)
                    converted[item[0]] = (item[1], item[2], item[3])
            elif len(item) == 3:
                # Assume (dir, type, expr) — key missing, use expr as key fallback
                converted[item[2]] = (item[0], item[1], item[2])
        arguments = converted
    # Defensive: accept dict-of-dicts {key: {"direction": ..., "type": ..., "value": ...}}
    if isinstance(arguments, dict):
        first_val = next(iter(arguments.values()), None)
        if isinstance(first_val, dict) and "direction" in first_val:
            converted = {}
            for k, v in arguments.items():
                converted[k] = (v["direction"], v["type"], v["value"])
            arguments = converted
    arg_lines = []
    for key, (direction, type_str, value_expr) in arguments.items():
        tag = {"In": "InArgument", "Out": "OutArgument", "InOut": "InOutArgument"}[direction]
        type_str = _normalize_type_arg(type_str)
        arg_lines.append(f'{i3}<{tag} x:TypeArguments="{type_str}" x:Key="{key}">[{_escape_vb_expr(value_expr)}]</{tag}>')
    args_block = "\n".join(arg_lines)
    return f"""{i}<ui:InvokeWorkflowFile ArgumentsVariable="{{x:Null}}" DisplayName="{dn}" WorkflowFileName="{wp}" UnSafe="False" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}">
{i2}<ui:InvokeWorkflowFile.Arguments>
{args_block}
{i2}</ui:InvokeWorkflowFile.Arguments>
{i}</ui:InvokeWorkflowFile>"""


def gen_invoke_code(code, id_ref, arguments=None, language="VBNet",
                    display_name="Invoke Code", indent="    "):
    """Generate InvokeCode — inline VB.NET or C# execution.

    Hallucination patterns prevented:
    - Missing XML encoding for code (newlines, quotes, angle brackets)
    - Wrong Language value (must be "CSharp" or "VBNet")
    - Using return statements (must assign to OutArgument variables)
    - Wrong argument syntax

    ⚠️ Prefer MultipleAssign for simple expression-based assignments.
    Only use InvokeCode for procedural logic (loops, Using, Try/Catch).

    Args:
        code: Raw code string — will be XML-encoded automatically
        arguments: List of (direction, type, key, variable) tuples.
                   direction: "In", "Out", "InOut"
                   e.g. [("In", "x:String", "str_input", "strInputVar"),
                         ("Out", "x:Int32", "int_result", "intOutputVar")]
        language: "VBNet" or "CSharp"
    """
    if not (language in ("VBNet", "CSharp")):
        raise ValueError(f"Invalid language: {language}")
    dn = _escape_xml_attr(display_name)
    i, i2, i3 = indent, indent+"  ", indent+"    "

    # XML-encode the code string
    encoded_code = (code
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "&#xA;")
        .replace("\t", "&#x9;"))

    if arguments:
        arg_lines = []
        dir_map = {"In": "InArgument", "Out": "OutArgument", "InOut": "InOutArgument"}
        for direction, arg_type, key, variable in arguments:
            tag = dir_map[direction]
            arg_lines.append(
                f'{i3}<{tag} x:TypeArguments="{arg_type}" x:Key="{key}">[{variable}]</{tag}>'
            )
        args_xml = "\n".join(arg_lines)
        return f"""{i}<ui:InvokeCode ContinueOnError="{{x:Null}}" Code="{encoded_code}" DisplayName="{dn}" Language="{language}" sap2010:WorkflowViewState.IdRef="InvokeCode_{id_ref}">
{i2}<ui:InvokeCode.Arguments>
{args_xml}
{i2}</ui:InvokeCode.Arguments>
{i}</ui:InvokeCode>"""
    else:
        return (
            f'{i}<ui:InvokeCode ContinueOnError="{{x:Null}}" Code="{encoded_code}" '
            f'DisplayName="{dn}" Language="{language}" '
            f'sap2010:WorkflowViewState.IdRef="InvokeCode_{id_ref}" />'
        )


def gen_invoke_method(method_name, id_ref, target_object=None, target_object_type=None,
                      target_type=None, parameters=None,
                      display_name="Invoke Method", indent="    "):
    """Generate InvokeMethod — call instance or static method.

    Hallucination patterns prevented:
    - Mixing TargetObject and TargetType (mutually exclusive)
    - Wrong parameter syntax (must be positional InArgument elements)

    Args:
        method_name: Method to call, e.g. "Add", "Sort", "Clear"
        target_object: (variable, type) for instance method, e.g. ("jArrItems", "njl:JArray")
        target_type: XAML type for static method, e.g. "sio:File"
        parameters: List of (type, variable) tuples for positional args,
                    e.g. [("njl:JObject", "jObjNew"), ("x:Boolean", "True")]
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3 = indent, indent+"  ", indent+"    "

    if not ((target_object is not None) != (target_type is not None)):
        raise ValueError("Must specify either target_object (instance) or target_type (static), not both")

    parts = [f'{i}<InvokeMethod DisplayName="{dn}" MethodName="{method_name}"']
    if target_type:
        parts[0] += f' TargetType="{target_type}"'
    parts[0] += f' sap2010:WorkflowViewState.IdRef="InvokeMethod_{id_ref}">'

    # TargetObject for instance method
    if target_object:
        var, typ = target_object
        parts.append(f"""{i2}<InvokeMethod.TargetObject>
{i3}<InArgument x:TypeArguments="{typ}">[{var}]</InArgument>
{i2}</InvokeMethod.TargetObject>""")

    # Positional parameters
    if parameters:
        for param_type, param_var in parameters:
            parts.append(f'{i2}<InArgument x:TypeArguments="{param_type}">[{param_var}]</InArgument>')

    parts.append(f'{i}</InvokeMethod>')
    return "\n".join(parts)
