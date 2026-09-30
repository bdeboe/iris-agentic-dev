/// Spec 132 fixture: an MCP service exposing IadAihub139.AuditToolSet.
Class IadAihub139.AuditMCP Extends %AI.MCP.Service [ DependsOn = IadAihub139.AuditToolSet ]
{

Parameter SPECIFICATION As STRING = "IadAihub139.AuditToolSet";

}
