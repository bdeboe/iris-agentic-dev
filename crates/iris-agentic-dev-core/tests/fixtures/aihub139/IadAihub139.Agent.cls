/// Spec 132 fixture: an agent whose provider comes from ConfigStore entry AI.LLM.IadAihub139LLM
/// and whose one tool comes from IadAihub139.ToolSet.
Class IadAihub139.Agent Extends %AI.Agent [ DependsOn = IadAihub139.ToolSet ]
{

Parameter PROVIDERCONFIG = "@{config:IadAihub139LLM}";

Parameter TOOLSETS = "IadAihub139.ToolSet";

XData INSTRUCTIONS [ MimeType = text/markdown ]
{
You reverse strings. When asked to reverse text, call the Reverse tool and reply with its result only.
}

}
