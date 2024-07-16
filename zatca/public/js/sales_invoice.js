frappe.ui.form.on('Sales Invoice', {
	on_submit(frm){
		frm.reload_doc();


	},
	refresh(frm) {
		if ((frm.doc.zatca_status=="Pending" || frm.doc.zatca_status=="Draft" || frm.doc.zatca_status=="Rejected" || frm.doc.zatca_status=="Cancelled")&& !frm.doc.simple){
		var print=document.querySelector('[data-original-title="Print"]');
		if (print){
		print.style.display="none";}
		var printa=document.querySelector('[data-original-title="طباعة"]');
		if (printa){
		printa.style.display="none";}
		}
		if(frm.doc.name.includes("new")){
			frm.doc.uuid="";
			frm.doc.hash="";
			frm.doc.xml_path="";
			frm.doc.qr_code_text="";
			frm.doc.zatca_status="Draft";
			frm.doc.custom_zatca_warnings="";
			frm.doc.custom_clearing_to_zatka_time=""
			frm.doc.custom_reporting_to_zatka_time=""
			refresh_field("uuid");
			refresh_field("hash")
			refresh_field("zatca_status");
			refresh_field("custom_zatca_warnings");
			refresh_field("custom_clearing_to_zatka_time");
			refresh_field("custom_reporting_to_zatka_time");
			frm.set_value("set_posting_time",0);
		};
		if ( frm.doc.docstatus==1  &&  (frm.doc.zatca_status=="Pending" || frm.doc.zatca_status=="Rejected"  || frm.doc.custom_zatca_warnings.includes("SANDBOX") ) ){
		frm.add_custom_button(__("Generate xml"), function() {
			frappe.call({
				method:"first_xml",
				doc:frm.doc,
				args:{"show_alert":true},
				callback(r){
					if(r.message){
						frm.reload_doc()
						//console.log(r.message)
						//let file_url = r.message.replace(/#/g, "%23");
						//window.open(file_url);

					}
				}
			})
		});}
		if (frm.doc.xml_path && frm.doc.xml_path!="" && frm.doc.xml_path!= null){
			frm.add_custom_button(__("Download xml"), function() {
				window.open(frm.doc.xml_path);

			})
		}
		if (frm.doc.xml_path && frm.doc.xml_path!="" && frm.doc.xml_path!= null  &&(frm.doc.zatca_status=="Pending" || frm.doc.zatca_status=="Rejected"  || frm.doc.custom_zatca_warnings.includes("SANDBOX")  ) ){
			frm.add_custom_button(__("Compliance Check"), function() {
				frappe.call({
					method:"compliance",
					doc:frm.doc,
					freeze:true,
					freeze_message:__("Verifying Invoice"),
					callback(r){
						if(r.message){
							
							//frm.reload_doc()
						}
					}
				})
				
			})
		}
		
		if ( frm.doc.docstatus==1 && frm.doc.simple  && frm.doc.xml_path!="" && frm.doc.xml_path!= null &&(frm.doc.zatca_status=="Pending" || frm.doc.zatca_status=="Rejected" || frm.doc.custom_zatca_warnings.includes("SANDBOX") )){
			frm.add_custom_button(__("Report to zatca"), function() {
				frappe.call({
					method:"report",
					doc:frm.doc,
					freeze:true,
					freeze_message:__("Reporting Invoice"),
					callback(r){
						if(r.message){
							
							frm.reload_doc()
						}
					}
				})
			})
		}
		if (frm.doc.docstatus==1 &&   !frm.doc.simple && frm.doc.xml_path!= null && frm.doc.xml_path!="" && (frm.doc.zatca_status=="Pending" || frm.doc.zatca_status=="Rejected" || frm.doc.custom_zatca_warnings.includes("SANDBOX"))){
			frm.add_custom_button(__("Clears"), function() {
				frappe.call({
					method:"clearance",
					freeze:true,
					freeze_message:__("Clearing Invoice"),
					doc:frm.doc,
					callback(r){
						if(r.message){
							frm.reload_doc();
						}
					}
				})
			})

		}

	},
	_set_posting_time :function(frm){
		if (frm.doc.set_posting_time){
			frappe.msgprint("You can't edit posting time")
			frm.set_value("set_posting_time",0)
		}
	},
	customer :function(frm){
		frappe.call({
			method:"set_type_based_on_customer",
			doc:frm.doc
		})


	}
})
