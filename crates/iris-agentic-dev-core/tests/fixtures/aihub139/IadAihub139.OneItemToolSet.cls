/// Spec 132 fixture: the same policy with one Blocked item. On 139 the list arrives empty, so
/// Reverse is not denied; %XML.Reader on the same XML gives Count() = 1.
Class IadAihub139.OneItemToolSet Extends %AI.ToolSet [ DependsOn = (IadAihub139.Tool, IadAihub139.DenyPolicy) ]
{

XData Definition [ MimeType = application/xml ]
{
<ToolSet Name="IadAihub139OneItem">
  <Policies>
    <Authorization Class="IadAihub139.DenyPolicy">
      <Blocked>Reverse</Blocked>
    </Authorization>
  </Policies>
  <Include Class="IadAihub139.Tool" />
</ToolSet>
}

}
