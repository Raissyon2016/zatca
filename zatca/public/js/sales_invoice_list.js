// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt
// render
//updated by Baha
setInterval(() => {
	$(".flash").each(function(i,obj) {
		var t= $(this).text();
		if (t!="Overdue"){
			t=parseInt(t.replace("m","").replace("h",""))
			if (t==0){
				$(this).text("Overdue");
			}else{
				$(this).text((t-1).toString()+"m");
			}
		}
	});
	
},60000);
frappe.listview_settings['Sales Invoice'] = {
	add_fields: ["customer", "customer_name", "base_grand_total", "outstanding_amount", "due_date", "company",
		"currency", "is_return","posting_date","posting_time","simple","zatca_status","xml_path","custom_zatca_warnings"],
	//hide_name_column:true,
	formatters:{
		zatca_status(val,field,doc){
			
			if (doc.zatca_status=="Draft"){
                                return "<span class='indicator-pill gray'>"+__(val)+"</span>"
                        }

			if (doc.zatca_status=="Cleared" || doc.zatca_status=="Reported"){
				return "<span class='indicator-pill green wow'>"+__(val)+"</span>"
			}
			if (doc.zatca_status=="Cleared with warnings" || doc.zatca_status=="Reported with warnings"){
                                return "<span class='indicator-pill green wow'>"+__(val)+"</span>"
                        }
			if (doc.zatca_status=="Rejected" || doc.zatca_status=="Overdue") {
				if (doc.simple  ){
					if (doc.posting_time[1]==":") {
						var d= new Date(doc.posting_date+"T0"+doc.posting_time.split(".")[0])
					}else{
						var d= new Date(doc.posting_date+"T"+doc.posting_time.split(".")[0])
					}
					console.log(doc.posting_date+"T"+doc.posting_time.split(".")[0])
					d.setDate(d.getDate()+1)
					var now = new Date(frappe.datetime.now_datetime())
					var left=(d-now)/3600000
					if (left>1 && left <24){
						val = __(val)+" ("+Math.floor(left)+__("h")+")" //+Math.floor((((d-now)/1000)%3600)/60)+"m)"
						return "<span class='indicator-pill orange'>"+__(val)+"</span>"
					}
					if (left>0 && left <1){
						val = (__(val)+" (<span class='flash blink'>"+Math.floor(left*60)+__("m")+"</span>)" )
						return "<span class='indicator-pill red'>"+__(val)+"</span>"
					}
					if (left<=0){
						return "<span class='indicator-pill red'>"+__(val)+" (<span class='flash blink'>"+__("Overdue")+"</span>)</span>"
					}
				}
                                return "<span class='indicator-pill red'>"+__(val)+"</span>"
                        }
			if (doc.zatca_status=="Pending" ){
				if (doc.simple){
					if (doc.posting_time[1]==":") {
						var d= new Date(doc.posting_date+"T0"+doc.posting_time)
					}else{
						var d= new Date(doc.posting_date+"T"+doc.posting_time)
					}
					d.setDate(d.getDate()+1)
					var now = new Date(frappe.datetime.now_datetime())
					var left=(d-now)/3600000
					
					if (left>1 && left <24){
						val = __(val)+" ("+Math.floor(left)+__("h")+")"  //+Math.floor((((d-now)/1000)%3600)/60)+"m)"
					}
					if (left>0 && left <1){
						val = __(val)+" (<span class='flash blink'>"+Math.floor(left*60)+__("m")+"</span>)" 
						return "<span class='indicator-pill orange'>"+__(val)+"</span>"
					}
					if (left<=0){
						return "<span class='indicator-pill red'>"+__(val)+" (<span class='flash blink'>"+__("Overdue")+"</span>)</span>"
					}
				}
                                return "<span class='indicator-pill yellow'>"+__(val)+"</span>"
                        }
			if (doc.zatca_status=="Cancelled"){
                                return "<span class='indicator-pill red'>"+__(val)+"</span>"
                        }




		}
	},
	get_indicator: function(doc) {
		const status_colors = {
			"Draft": "grey",
			"Unpaid": "orange",
			"Paid": "green",
			"Return": "gray",
			"Credit Note Issued": "gray",
			"Unpaid and Discounted": "orange",
			"Partly Paid and Discounted": "yellow",
			"Overdue and Discounted": "red",
			"Overdue": "red",
			"Partly Paid": "yellow",
			"Internal Transfer": "darkgrey"
		};
		return [__(doc.status), status_colors[doc.status], "status,=,"+doc.status];
	},
	right_column: "grand_total",
	onload: function(listview) {
		listview.page.add_action_item(__("Delivery Note"), ()=>{
			erpnext.bulk_transaction_processing.create(listview, "Sales Invoice", "Delivery Note");
		});
		listview.page.add_menu_item(__("Report Pending Invoices"), ()=>{
			
			frappe.call({
                                        method:"zatca.overrides.sales_invoice.report_all",
                                        freeze:true,
                                        freeze_message:__("Sending Invoices..."),
                                        callback(r){
                                                if(r.message){
                                                        console.log(r.message);
                                                }
                                        }
                                })
		});
		listview.page.add_action_item(__("Report to ZATCA"), ()=>{
			var items=[]
			for (var i=0;i<listview.$checks.length;i=i+1){
				items.push(listview.$checks[i].dataset.name)
			}
			frappe.call({
                                        method:"zatca.overrides.sales_invoice.report_all",
                                        args:{"items":items},
                                        callback(r){
                                                if(r.message){
                                                        console.log(r.message);
                                                }
                                        }
                                })
		});
		listview.page.add_action_item(__("Payment"), ()=>{
			erpnext.bulk_transaction_processing.create(listview, "Sales Invoice", "Payment Entry");
		});
	},
	button: {
        show(doc) {
            return ((doc.xml_path!= null && doc.xml_path!="" && (doc.zatca_status=="Pending" || doc.zatca_status=="Rejected" || doc.custom_zatca_warnings.includes("SANDBOX") )))
        },
        get_label(doc) {
        if ((doc.xml_path!= null && doc.xml_path!="" && (doc.zatca_status=="Pending" || doc.zatca_status=="Rejected" || doc.custom_zatca_warnings.includes("SANDBOX") ))){
            if (doc.simple){
            	return __("Report")
            }else{
            	return __("Clears")
            }}
            else{
            return("<svg class='icon icon-sm' style=''>  <use class='' href='#icon-printer'></use>  </svg>")
            }
        },
        get_description(doc) {
        	if (doc.simple){
            	return __('Report {0} to ZATCA', [`${doc.name}`])
            }else{
            	return __('Clear {0} to ZATCA', [`${doc.name}`])
            }
        },
        action(doc) {
        if ((doc.xml_path!= null && doc.xml_path!="" && (doc.zatca_status=="Pending" || doc.zatca_status=="Rejected" || doc.custom_zatca_warnings.includes("SANDBOX") ))){
            frappe.call({
                                        method:"zatca.overrides.sales_invoice.clears_report",
                                        args:{"invoice":doc.name},
                                        callback(r){
                                        	console.log(r.message)
                                        }
                                })
        }
        else{
        	window.open("/app/print/Sales Invoice/"+doc.name)
        }
    }},
    
    
};
