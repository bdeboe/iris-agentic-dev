/// Spec 132 fixture: a ToolSet that includes IadAihub139.Tool.
Class IadAihub139.ToolSet Extends %AI.ToolSet [ DependsOn = IadAihub139.Tool ]
{

XData Definition [ MimeType = application/xml ]
{
<ToolSet Name="IadAihub139">
  <Description>Spec 132 fixture tools</Description>
  <Include Class="IadAihub139.Tool" />
</ToolSet>
}

}
