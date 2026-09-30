Include %AI

/// Spec 132 fixture: an XML-configurable authorization policy that denies the tools it lists.
Class IadAihub139.DenyPolicy Extends (%AI.Policy.Authorization, %XML.Adaptor)
{

Parameter XMLNAME = "Authorization";

Property Blocked As list Of %String(MAXLEN = "", XMLITEMNAME = "Blocked", XMLPROJECTION = "ELEMENT");

Method %CanExecute(tool As %String, call As %DynamicObject, metadata As %DynamicObject) As %Status
{
    Set sc = $$$OK
    For i = 1:1:..Blocked.Count() {
        If tool [ ..Blocked.GetAt(i) {
            Set sc = $$$ERROR($$$AICoreToolAccessDenied, "blocked by IadAihub139.DenyPolicy: " _ tool)
            Quit
        }
    }
    Return sc
}

}
