# Copyright (c) 2023, Weslati Baha Eddine and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	green="#15d636"
	columns, data = [], []
	columns=get_columns(filters)
	fil=[["posting_date","between",[filters["from_date"],filters["to_date"]]],["docstatus","in",[1]]]
	if "zatca_status" in filters.keys() and filters["zatca_status"]:
		fil.append(["zatca_status","in",[filters["zatca_status"]]])
	if "type" in filters.keys() and filters["type"]:
		if filters["type"]=="Simple Invoices":
			fil.append(["simple","in",[1]])
		else:
			fil.append(["simple","in",[0]])
	invoices=frappe.db.get_all("Sales Invoice",filters=fil,fields=["name","status","zatca_status","total_taxes_and_charges","grand_total","customer","custom_clearing_to_zatka_time","custom_reporting_to_zatka_time"])
	cleared=0
	reported=0
	clearedw=0
	reportedw=0
	rejected=0
	pending=0
	for d in invoices:
		if d["zatca_status"]=="Cleared":
			
			d["zatca_status"]="<span style='color:green;'>"+_(d["zatca_status"])+"</span>"
			cleared+=1
		elif d["zatca_status"]=="Reported":
			d["custom_clearing_to_zatka_time"]=d["custom_reporting_to_zatka_time"]
			d["zatca_status"]="<span style='color:green;'>"+_(d["zatca_status"])+"</span>"
			reported+=1
		elif d["zatca_status"]=="Reported with warnings":
			d["custom_clearing_to_zatka_time"]=d["custom_reporting_to_zatka_time"]
			d["zatca_status"]="<span style='color:green;'>"+_(d["zatca_status"])+"</span>"
			reportedw+=1
		elif d["zatca_status"]=="Cleared with warnings":
			d["zatca_status"]="<span style='color:green;'>"+_(d["zatca_status"])+"</span>"
			clearedw+=1
		elif d["zatca_status"]=="Rejected":
			d["zatca_status"]="<span style='color:red;'>"+_("Rejected")+"</span>"
			rejected+=1
		elif d["zatca_status"]=="Pending":
			d["zatca_status"]="<span style='color:#fce303;'>"+_("Pending")+"</span>"
			pending+=1
		else:
			a=1
	if "type" in filters.keys() and filters["type"]:
		if filters["type"]=="Simple Invoices":
			chart = {'data':{'labels':["Reported","Rejected","Pending"],'datasets':[{'name':'Invoices','values':[reported+reportedw,rejected,pending]} ]},'type':'donut',"colors":[green,"#fc3503","#fce303"]}
		else:
			chart = {'data':{'labels':["Cleared","Rejected","Pending"],'datasets':[{'name':'Invoices','values':[cleared+clearedw,rejected,pending]} ]},'type':'donut',"colors":[green,"#fc3503","#fce303"]}
	else:
		chart = {'data':{'labels':["Reported","Cleared","Rejected","Pending"],'datasets':[{'name':'Invoices','values':[reported+reportedw,cleared+clearedw,rejected,pending]} ]},'type':'percentage',"colors":["#13d627","#13d688","#fc3503","#fce303"]}
	report_summary = [	{"label":"Reported & Cleared","value":cleared+reported+reportedw+clearedw,'indicator':'Blue',"width":50},
				{"label":"Pending","value":pending,'indicator':'yellow',"width":50},
				{"label":"Rejected","value":rejected,'indicator':'red',"width":50}
	 ]
	return columns, invoices, None,chart,None
	
	
	
	
	
def get_columns(filters=None):
	columns=[
		{
            'fieldname': 'name',
            'label': _('Invoice'),
            'fieldtype': 'Link',
            'options': 'Sales Invoice'
        },
	{
            'fieldname': 'customer',
            'label': _('Customer'),
            'fieldtype': 'Link',
            'options': 'Customer',
            'width':150,
        },
	{
            'fieldname': 'zatca_status',
            'label': _('Zatca Status'),
            'fieldtype': 'Data',
            'width':180,
           
        }
	,
	{
            'fieldname': 'custom_clearing_to_zatka_time',
            'label': _('Reporting/ Clearing time'),
            'fieldtype': 'Datetime',
            'width':180,
           
        }
	
	]
	return columns
