/// HTMX front end for Demo.Todo. Every endpoint returns HTML, not JSON, so the page
/// needs no JavaScript of its own. Built with iris-agentic-dev as a live demo.
Class Demo.TodoREST Extends %CSP.REST
{

Parameter CHARSET = "utf-8";

Parameter CONTENTTYPE = "text/html";

Parameter HandleCorsRequest = 1;

XData UrlMap [ XMLNamespace = "http://www.intersystems.com/urlmap" ]
{
<Routes>
<Route Url="/" Method="GET" Call="Index"/>
<Route Url="/rows" Method="GET" Call="Rows"/>
<Route Url="/add" Method="POST" Call="Add"/>
<Route Url="/toggle/:id" Method="POST" Call="Toggle"/>
<Route Url="/del/:id" Method="DELETE" Call="Del"/>
</Routes>
}

/// The whole page. The list itself comes from Rows(), so there is one renderer, not two.
ClassMethod Index() As %Status
{
	Set tSC = $$$OK
	Try {
		Do %response.SetHeader("Cache-Control", "no-store")
		Write "<!DOCTYPE html>", !
		Write "<html lang='en'><head><meta charset='utf-8'>", !
		Write "<title>IRIS Todo</title>", !
		Write "<script src='https://unpkg.com/htmx.org@1.9.12'></script>", !
		Write "<style>", !
		Write "body{font:16px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
		Write "max-width:40rem;margin:3rem auto;padding:0 1rem;color:#1b1b1b}", !
		Write "h1{font-size:1.4rem;margin-bottom:.2rem}", !
		Write ".sub{color:#666;font-size:.85rem;margin-bottom:1.5rem}", !
		Write "form{display:flex;gap:.5rem;margin-bottom:1.5rem}", !
		Write "input[type=text]{flex:1;padding:.55rem;border:1px solid #ccc;border-radius:6px}", !
		Write "select,button{padding:.55rem;border:1px solid #ccc;border-radius:6px;background:#fff}", !
		Write "button{cursor:pointer}", !
		Write "ul{list-style:none;padding:0}", !
		Write "li{display:flex;align-items:center;gap:.6rem;padding:.6rem .2rem;"
		Write "border-bottom:1px solid #eee}", !
		Write ".t{flex:1}", !
		Write ".done .t{text-decoration:line-through;color:#999}", !
		Write ".p{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;"
		Write "padding:.1rem .4rem;border-radius:4px;background:#eee;color:#555}", !
		Write ".p.high{background:#ffe0e0;color:#a30000}", !
		Write ".p.low{background:#eef;color:#445}", !
		Write ".x{border:0;background:none;color:#bbb;font-size:1.1rem}", !
		Write ".x:hover{color:#a30000}", !
		Write "</style></head><body>", !
		Write "<h1>Todo</h1>", !
		Write "<div class='sub'>Rows live in the <code>Demo.Todo</code> table in IRIS.</div>", !
		Write "<form hx-post='add' hx-target='#list' hx-swap='innerHTML' hx-on::after-request='this.reset()'>", !
		Write "<input type='text' name='title' placeholder='What needs doing?' required>", !
		Write "<select name='priority'>", !
		Write "<option value='normal' selected>normal</option>", !
		Write "<option value='high'>high</option>", !
		Write "<option value='low'>low</option>", !
		Write "</select>", !
		Write "<button type='submit'>Add</button>", !
		Write "</form>", !
		Write "<div id='list' hx-get='rows' hx-trigger='load'></div>", !
		Write "</body></html>", !
	}
	Catch tEx {
		Set tSC = tEx.AsStatus()
	}
	Quit tSC
}

/// The list fragment. Every mutating endpoint ends here, so the page and the swaps agree.
ClassMethod Rows() As %Status
{
	Set tSC = $$$OK
	Try {
		Do %response.SetHeader("Cache-Control", "no-store")
		Set tOutstanding = ##class(Demo.Todo).Outstanding()
		Write "<div class='sub'>", tOutstanding, " outstanding</div>", !
		Write "<ul>", !
		Set tStatement = ##class(%SQL.Statement).%New()
		Set tSC = tStatement.%Prepare("SELECT ID, Title, Priority, Done FROM Demo.Todo ORDER BY Done, ID")
		If $$$ISERR(tSC) {
			Return tSC
		}
		Set tRS = tStatement.%Execute()
		While tRS.%Next() {
			Set tId = tRS.%Get("ID")
			Set tTitle = $ZConvert(tRS.%Get("Title"), "O", "HTML")
			Set tPriority = $ZConvert(tRS.%Get("Priority"), "O", "HTML")
			Set tDone = tRS.%Get("Done")
			Write "<li class='", $Select(tDone: "done", 1: ""), "'>", !
			Write "<input type='checkbox' hx-post='toggle/", tId, "' hx-target='#list' "
			Write "hx-swap='innerHTML'", $Select(tDone: " checked", 1: ""), ">", !
			Write "<span class='t'>", tTitle, "</span>", !
			Write "<span class='p ", tPriority, "'>", tPriority, "</span>", !
			Write "<button class='x' hx-delete='del/", tId, "' hx-target='#list' "
			Write "hx-swap='innerHTML' title='Delete'>&times;</button>", !
			Write "</li>", !
		}
		Write "</ul>", !
		If tOutstanding = 0 {
			Write "<div class='sub'>Nothing outstanding.</div>", !
		}
	}
	Catch tEx {
		Set tSC = tEx.AsStatus()
	}
	Quit tSC
}

/// Add from the form, then re-render the list.
ClassMethod Add() As %Status
{
	Set tSC = $$$OK
	Try {
		Set tTitle = $Get(%request.Data("title", 1))
		Set tPriority = $Get(%request.Data("priority", 1), "normal")
		If tTitle '= "" {
			Set tSC = ##class(Demo.Todo).Add(tTitle, tPriority, .tId)
			If $$$ISERR(tSC) {
				Return tSC
			}
		}
		Set tSC = ..Rows()
	}
	Catch tEx {
		Set tSC = tEx.AsStatus()
	}
	Quit tSC
}

/// Flip one item, then re-render the list.
ClassMethod Toggle(pId As %String) As %Status
{
	Set tSC = $$$OK
	Try {
		Set tSC = ##class(Demo.Todo).Toggle(pId)
		If $$$ISERR(tSC) {
			Return tSC
		}
		Set tSC = ..Rows()
	}
	Catch tEx {
		Set tSC = tEx.AsStatus()
	}
	Quit tSC
}

/// Delete one item, then re-render the list.
ClassMethod Del(pId As %String) As %Status
{
	Set tSC = $$$OK
	Try {
		Set tSC = ##class(Demo.Todo).%DeleteId(pId)
		If $$$ISERR(tSC) {
			Return tSC
		}
		Set tSC = ..Rows()
	}
	Catch tEx {
		Set tSC = tEx.AsStatus()
	}
	Quit tSC
}

}

