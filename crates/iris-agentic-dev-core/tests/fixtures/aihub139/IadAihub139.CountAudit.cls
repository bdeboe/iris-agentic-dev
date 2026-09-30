/// Spec 132 fixture: an audit policy that counts calls and records the last tool name.
Class IadAihub139.CountAudit Extends %AI.Policy.Audit
{

Property Calls As %Integer [ InitialExpression = 0 ];

Property LastTool As %String(MAXLEN = "");

Method %LogExecution(call As %DynamicObject, metadata As %DynamicObject, result As %DynamicObject, duration As %Integer, status As %Status) As %Status
{
    Set ..Calls = ..Calls + 1
    Set ..LastTool = call.name
    Return $$$OK
}

}
