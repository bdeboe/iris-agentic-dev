/// Spec 132 fixture: %AI.Policy.ConsoleAudit, plus a record in ^IadAihub139("audit") of each call
/// and the device it wrote to, so a test can see that the console audit ran.
Class IadAihub139.GlobalAudit Extends %AI.Policy.ConsoleAudit
{

Method %LogExecution(call As %DynamicObject, metadata As %DynamicObject, result As %DynamicObject, duration As %Integer, status As %Status) As %Status
{
    Set sc = ##super(call, metadata, result, duration, status)
    Set ^IadAihub139("audit", $Increment(^IadAihub139("audit"))) = call.name _ " " _ $IO
    Return sc
}

}
