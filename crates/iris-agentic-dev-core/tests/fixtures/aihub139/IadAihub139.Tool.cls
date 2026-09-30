/// Spec 132 fixture: one %AI.Tool with one tool method, no side effects.
Class IadAihub139.Tool Extends %AI.Tool
{

Property Name As %String [ InitialExpression = "IadAihub139 Reverse" ];

Property Description As %String(MAXLEN = "") [ InitialExpression = "Reverse a string" ];

/// Return the text reversed.
/// text: the string to reverse
ClassMethod Reverse(text As %String) As %String
{
    Return $Reverse(text)
}

}
