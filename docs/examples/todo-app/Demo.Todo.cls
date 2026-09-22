/// A todo item. Created with iris-agentic-dev as a live demo of the agentic tools.
Class Demo.Todo Extends %Persistent
{

Property Title As %String(MAXLEN = 200) [ Required ];

Property Done As %Boolean [ InitialExpression = 0 ];

Property Priority As %String(VALUELIST = ",low,normal,high") [ InitialExpression = "normal" ];

Property Created As %TimeStamp [ InitialExpression = {$ZDateTime($Horolog, 3)} ];

Index DoneIdx On Done;

/// Add one item. Returns the status; the new id comes back in pId.
ClassMethod Add(pTitle As %String, pPriority As %String = "normal", Output pId As %Integer) As %Status
{
	Set tSC = $$$OK
	Set pId = ""
	Try {
		Set tTitle = $ZStrip(pTitle, "<>W")
		If tTitle = "" {
			Set tSC = $$$ERROR($$$GeneralError, "Title is required")
			Return tSC
		}
		Set tTodo = ..%New()
		Set tTodo.Title = tTitle
		Set tTodo.Priority = pPriority
		Set tSC = tTodo.%Save()
		If $$$ISERR(tSC) {
			Return tSC
		}
		Set pId = tTodo.%Id()
	}
	Catch tEx {
		Set tSC = tEx.AsStatus()
	}
	Quit tSC
}

/// Flip Done on one item.
ClassMethod Toggle(pId As %Integer) As %Status
{
	Set tSC = $$$OK
	Try {
		Set tTodo = ..%OpenId(pId, , .tSC)
		If '$IsObject(tTodo) {
			Set tSC = $$$ERROR($$$GeneralError, "No todo with id " _ pId)
			Return tSC
		}
		Set tTodo.Done = 'tTodo.Done
		Set tSC = tTodo.%Save()
	}
	Catch tEx {
		Set tSC = tEx.AsStatus()
	}
	Quit tSC
}

/// How many are left. Used by the header count in the UI.
ClassMethod Outstanding() As %Integer
{
	Set tCount = 0
	Try {
		&sql(SELECT COUNT(*) INTO :tCount FROM Demo.Todo WHERE Done = 0)
		If SQLCODE < 0 {
			Set tCount = 0
		}
	}
	Catch {
		Set tCount = 0
	}
	Quit tCount
}

Storage Default
{
<Data name="TodoDefaultData">
<Value name="1">
<Value>%%CLASSNAME</Value>
</Value>
<Value name="2">
<Value>Title</Value>
</Value>
<Value name="3">
<Value>Done</Value>
</Value>
<Value name="4">
<Value>Priority</Value>
</Value>
<Value name="5">
<Value>Created</Value>
</Value>
</Data>
<DataLocation>^Demo.TodoD</DataLocation>
<DefaultData>TodoDefaultData</DefaultData>
<IdLocation>^Demo.TodoD</IdLocation>
<IndexLocation>^Demo.TodoI</IndexLocation>
<StreamLocation>^Demo.TodoS</StreamLocation>
<Type>%Storage.Persistent</Type>
}

}

