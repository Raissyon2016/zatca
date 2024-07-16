// Copyright (c) 2023, Weslati Baha Eddine and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Sales Invoices and Zatca"] = {
	"filters": [
		{
            "fieldname": 'company',
            "label": __('Company'),
            "fieldtype": 'Link',
            "options": 'Company',
            "default": frappe.defaults.get_user_default('company')
        },
        {
		"fieldname":"from_date",
		"label": __("From Date"),
		"fieldtype": "Date",
		"default": frappe.datetime.week_start(),
		"reqd": 1,
		"width": "60px"
		},
		{
		"fieldname":"to_date",
		"label": __("To Date"),
		"fieldtype": "Date",
		"default": frappe.datetime.add_days(frappe.datetime.week_start(), 7),
		"reqd": 1,
		"width": "60px"
		},
		{
		"fieldname":"type",
		"label": __("Invoice Type"),
		"fieldtype": "Select",
		"options":[
		"",
				{
					label: __("Standard Invoices"),
					value: "Standard Invoices",
				},
				{
					label: __("Simple Invoices"),
					value: "Simple Invoices",
				},
			],
		"width": "60px"
		},
		{
		"fieldname":"zatca_status",
		"label": __("Zatca Status"),
		"fieldtype": "Select",
		"options":["","Pending","Cleared","Cleared with warnings","Reported","Reported with warnings","Rejected"],
		"width": "60px"
		},
	]
};
