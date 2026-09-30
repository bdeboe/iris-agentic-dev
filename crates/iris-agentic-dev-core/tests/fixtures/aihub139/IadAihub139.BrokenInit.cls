/// Spec 132 fixture: the %OnInit guard from ai-hub-eap's own agent skill (its SKILL.md line 148), unparenthesised.
/// ObjectScript evaluates left to right, so the guard is always true and a provider the caller passed
/// to %New() is replaced by the ConfigStore one.
Class IadAihub139.BrokenInit Extends %AI.Agent
{

Parameter MODELCONFIGNAME = "IadAihub139LLM";

Method %OnInit() As %Status
{
    Set sc = $$$OK
    Try {
        If ..Provider = "" && ..#MODELCONFIGNAME '= "" {
            Do ##class(%AI.Utils.SettingStore).RegisterDefaults()
            Set settings = {}.%FromJSON(##class(%AI.Utils.SettingStore).Expand("@{config:" _ ..#MODELCONFIGNAME _ "}"))
            Set ..Provider = ##class(%AI.Provider).Create(settings."model_provider", settings)
            Set ..Model = settings.model
        }
    } Catch ex {
        Set sc = ex.AsStatus()
    }
    Return sc
}

}
