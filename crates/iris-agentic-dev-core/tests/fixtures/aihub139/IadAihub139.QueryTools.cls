/// Spec 132 fixture: a Query tool, an Include and an Exclude, for the hackathon ToolSet claims.
Class IadAihub139.QueryTools Extends %AI.ToolSet [ DependsOn = IadAihub139.Tool ]
{

XData Definition [ MimeType = application/xml ]
{
<ToolSet Name="IadAihub139Query">
  <Description>Spec 132 fixture query tools</Description>
  <Query Name="ListTables" Description="List tables in one schema." Arguments="schema As %String, minLen As %Integer = 0, views As %Boolean = 0" MaxRows="1">
    <![CDATA[
      SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
      WHERE TABLE_SCHEMA = :schema AND LENGTH(TABLE_NAME) >= :minLen AND (:views = 0 OR TABLE_TYPE = 'VIEW')
    ]]>
  </Query>
  <Include Class="IadAihub139.Tool" />
  <Exclude Tool="Reverse" />
</ToolSet>
}

}
