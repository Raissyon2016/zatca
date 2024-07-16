from . import __version__ as app_version

app_name = "zatca"
app_title = "Zatca"
app_publisher = "Weslati Baha Eddine"
app_description = "zatca"
app_icon = "octicon octicon-file-directory"
app_color = "blue"
app_email = "weslatibahaou@gmail.com"
app_license = "MIT"


after_install="zatca.overrides.address.setup"
doctype_js = {"Sales Invoice" : "public/js/sales_invoice.js","Company":"public/js/company.js"}
doctype_list_js = {"Sales Invoice":"public/js/sales_invoice_list.js","Company":"public/js/company_list.js"}
#app_include_css = ["/assets/zatca/css/jquery.shining.css",  "/assets/zatca/css/jquery.shining.min.css"]
app_include_css = ["/assets/zatca/css/zatca.css"]
app_include_js = ["/assets/zatca/js/custom.js"]

override_doctype_class = {
	"Company":"zatca.overrides.company.CustomCompany",
	"Sales Invoice":"zatca.overrides.sales_invoice.CustomSalesInvoice",
	"Address":"zatca.overrides.address.CustomAddress",
	"Item":"zatca.overrides.item.CustomItem"
}

fixtures = [
	{"dt":"Custom Field","filters":[["dt","in",["Sales Invoice","Company","Address","Sales Invoice Item","Customer","Item"]]]}
	,"Translation"
	,"VAT category"
	
	,{"dt":"Role","filters":[["name","in",["Zatca Manager","Accounts Manager"]]]}
	,{"dt":"Custom DocPerm","filters":[["role","in",["Zatca Manager","Accounts Manager"]]]},
	
	{"dt":"List Filter","filters":[["reference_doctype","in",["Sales Invoice"]]]}
	]


scheduler_events = {
	"hourly": [
		"zatca.overrides.sales_invoice.clear_report_invoices_hourly"
	],
	"cron": {
		"*/5 * * * * ":[
			"zatca.overrides.sales_invoice.set_overdue"
		],
		"55 23 * * * ":[
			"zatca.overrides.sales_invoice.clear_report_invoices"
		]
	}

}
