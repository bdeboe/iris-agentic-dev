/// Spec 132 fixture: a ToolSet-local authorization policy configured in XML. Two Blocked items,
/// because 139's loader drops a one-item list (see IadAihub139.OneItemToolSet).
Class IadAihub139.PolicyToolSet Extends %AI.ToolSet [ DependsOn = (IadAihub139.Tool, IadAihub139.DenyPolicy) ]
{

XData Definition [ MimeType = application/xml ]
{
<ToolSet Name="IadAihub139Policy">
  <Description>Spec 132 fixture with a ToolSet-local policy</Description>
  <Policies>
    <Authorization Class="IadAihub139.DenyPolicy">
      <Blocked>Reverse</Blocked>
      <Blocked>NoSuchTool</Blocked>
    </Authorization>
  </Policies>
  <Include Class="IadAihub139.Tool" />
</ToolSet>
}

}
