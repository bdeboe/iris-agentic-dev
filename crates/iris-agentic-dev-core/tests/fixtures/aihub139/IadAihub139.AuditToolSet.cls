/// Spec 132 fixture: a ToolSet whose local audit policy writes to the current device.
Class IadAihub139.AuditToolSet Extends %AI.ToolSet [ DependsOn = (IadAihub139.Tool, IadAihub139.GlobalAudit) ]
{

XData Definition [ MimeType = application/xml ]
{
<ToolSet Name="IadAihub139Audit">
  <Policies>
    <Audit Class="IadAihub139.GlobalAudit" />
  </Policies>
  <Include Class="IadAihub139.Tool" />
</ToolSet>
}

}
