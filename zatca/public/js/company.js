frappe.ui.form.on('Company', { 
	onload: function (frm) {
	var ad = frm.doc.custom_short_address;
		if (ad.length!=8 || ad.slice(0,4).toUpperCase() != ad.slice(0,4) || !isNumeric(ad.slice(4,8)) ){
		   frm.set_intro(__('The short address must consists of 4 letters and 4 numbers.example : RRRD2929'), 'orange');
		   $("#wrong_address").show();
	}
	var id = frm.doc.tax_id;
		if (id.length!=15 || id[0]!="3" || id.at(-1)!="3" || !isNumeric(id)){
			frm.set_intro(__('Tax id must be 15 digits, begins with 3 and ends with 3.'), 'orange');
			$("#wrong_tax").show();
		}
	},
	tax_id: function(frm){
		var id = frm.doc.tax_id;
		if (id.length!=15 || id[0]!="3" || id.at(-1)!="3" || !isNumeric(id)){
			$("#wrong_tax").show();
		}
		else{
			$("#wrong_tax").hide();
			frm.set_intro();
		}
	},
	custom_short_address: function(frm){
		var ad = frm.doc.custom_short_address;
		if (ad.length!=8 || ad.slice(0,4).toUpperCase() != ad.slice(0,4) || !isNumeric(ad.slice(4,8)) ){
			$("#wrong_address").show();
			frappe.validated=false;
			return
		}
		else{
			$("#wrong_address").hide();
			frm.set_intro();
		}
	},
	before_save(frm){
	var id = frm.doc.tax_id;
	if (id.length!=15 || id[0]!="3" || id.at(-1)!="3" || !isNumeric(id)){
			$("#wrong_tax").show();
			$("[data-fieldname=tax_id]").focus()
		}
	},
	refresh(frm) { 
		if (frappe.user.has_role("Zatca Manager")){	
			if (!frm.doc.csr){
				frm.add_custom_button(__("Generate CSR"), function() {
					let d = new frappe.ui.Dialog({
						title:__("Important"),
						fields:[
							{label:"Notes",fieldname:"note",fieldtype:"HTML",options:getnotes()},
							
						],
						primary_action_label: __("Continue"),
						primary_action(values){
							csr_dialog(frm);
							d.hide();
						}

					})
					d.show();
				},__("Zatca"));
				frm.add_custom_button(__("Insert CSR"), function() {
					let d = new frappe.ui.Dialog({
						title:__("Important"),
						fields:[
							{label:"Type",fieldname:"type",fieldtype:"Select",default:"Text",options:["Text","base64 encoded"]},
							{label:"Notes",fieldname:"note",fieldtype:"HTML",options:""},
							{label:"CSR",fieldname:"csr",fieldtype:"Long Text"},
							{label:"Restart PIH",fieldname:"restart_pih",fieldtype:"Check",default:1},
							{label:"I agree",fieldname:"agree",fieldtype:"Check"},
							
						],
						primary_action_label: __("Continue"),
						primary_action(values){
							
							//console.log(values),
							if (values["agree"] && values["csr"]){
							insert_csr(frm,values);
							d.hide();
							}else{
							if (!values["csr"]){
								frappe.show_alert({message:__("CSR is missing"),indicator:"yellow",seconds:3})
							}else{
							if (!values["agree"]){
								frappe.show_alert({message:__("Do you agree?"),indicator:"yellow",seconds:3})
							}}
							}
						}

					})
					d.show();
				},__("Zatca"))
			}
			else{
			if (frm.doc.ccsid_requestid){
				if (frm.doc.pcsid_requestid){
				frm.add_custom_button(__("Renewal"), function() {
					let d = new frappe.ui.Dialog({
						title:__("Important"),
						fields:[
							{label:"Notes",fieldname:"note",fieldtype:"HTML",options:getrenewalnotes()},
							{label:"OTP",fieldname:"otp",fieldtype:"Data",default:frm.doc.otp},
							
						],
						primary_action_label: __("Continue"),
						primary_action(values){
							if (values["otp"]){
								if (values["otp"].length!=6 || !isNumeric(values["otp"])){
										frappe.show_alert({message:__("OTP must be a 6 digits number."),indicator:"yellow",seconds:3})
									}else{
								if (values["otp"]==frm.doc.otp){
									frappe.show_alert({message:__("New OTP can not be the same as old OTP."),indicator:"yellow",seconds:3})	
								}else{
								frappe.call({
									method:"zatca.api.renew",
									args:{"company":frm.doc.name,"new_otp":values["otp"]},
									freeze:true,
									freeze_message:__("Renewing Certificate..."),
									callback(r){
										console.log(r.message)
										if (r.message=="1"){
											//frm.reload_doc()
										}
									}
								})
								d.hide();
							}}
							}else{
								frappe.show_alert({message:__("Missing OTP"),indicator:"yellow",seconds:3})
							}
						}
					})
					d.show();	



				},__("Zatca"))
			}}else{
				frm.add_custom_button(__("Onboarding"), function() {
					let d = new frappe.ui.Dialog({
						title:__("Important"),
						fields:[
							{label:"Notes",fieldname:"note",fieldtype:"HTML",options:getonboardingnotes()},
							{label:"OTP",fieldname:"otp",fieldtype:"Data",default:frm.doc.otp},
							{label:__("Onboarding using ")+"<b>"+__(frm.doc.custom_api_endpoint)+"</b>"+__(" mode?"),fieldname:"check",fieldtype:"Check"},
							
						],
						primary_action_label: __("Continue"),
						primary_action(values){
							if (values["check"]){
								if (values["otp"]){
									if (values["otp"].length!=6 || !isNumeric(values["otp"])){
										frappe.show_alert({message:__("OTP must be a 6 digits number."),indicator:"yellow",seconds:3})
									}else{
										frappe.call({
											method:"zatca.api.onboarding",
											args:{"company":frm.doc.name,"new_otp":values["otp"]},
											freeze:true,
											freeze_message:__("Onboarding..."),
											callback(r){
												console.log(r.message)
												if (r.message=="1"){
													//frm.reload_doc()
												}
											}
										})
										d.hide();
								}
								}else{
									frappe.show_alert({message:__("Missing OTP"),indicator:"yellow",seconds:3})
								}
							}else{
								frappe.show_alert({message:__("Do you agree?"),indicator:"yellow",seconds:3})
							}
						}
					})
					d.show();


				},__("Zatca"))
			
			
			}
			
			
			frm.add_custom_button(__("Copy CSR"), function() {
					navigator.clipboard.writeText(atob(frm.doc.csr));
					frappe.show_alert({"message":__("Copied to clipboard."),"indicator":"green"})
				},__("Zatca"))
			
			
			
			
			
			frm.add_custom_button(__("Clear"), function() {
				frappe.call({
					method:"zatca.api.clear",
					args:{"company":frm.doc.name},
					callback(r){
						if (r.message){
							
						}
					}
				})
			},__("Zatca"))
	}
	
	frm.add_custom_button(__("Restart Fatoora Transactions"), function() {
		if (frm.doc.custom_zatca_status=="Enabled"){
			frappe.msgprint(__("This action only works when zatca is disabled."))
		}else{
		let d = new frappe.ui.Dialog({
						title:__("Important"),
						fields:[
							{label:"Notes",fieldname:"note",fieldtype:"HTML",options:restart()},
							{label:"I agree",fieldname:"agree",fieldtype:"Check"},
							{label:"Company Name",fieldname:"company_name",fieldtype:"Data",mandatory:1}
						],
						primary_action_label: __("Continue"),
						primary_action(values){
							if (values["agree"]){
								if (values["company_name"]){
									frappe.call({
										doc:frm.doc,
										args:{"values":values},
										method:"restart",
										freeze:true,
										freeze_message:__("Restarting transactions"),
										callback(r){
											if(r.message=="1"){
												
											}
										}
									})
									d.hide()
								}
								else{
									frappe.show_alert({message:__("Enter the ecompany name to confirm."),indicator:"yellow",seconds:3})
								}
							
							}else{
								frappe.show_alert({message:__("Do you agree?"),indicator:"yellow",seconds:3})
							}
						}

					})
					d.show();
	}
	},__("Zatca"))
	}}
})


function getnotes(){
	let notes=__("As a part of the first-time onboarding and renewal process, the Taxpayer's EGS Unit(s) must submit a CSR to the E-invoicing Platform once an OTP is entered into the EGS unit. The CSR is an encoded text that the EGS Unit(s) submits to the E-invoicing Platform and the ZATCA CA in order to receive a Compliance CSID, which is a self-signed certificate issued by the E-invoicing Platform allowing clients to continue the Onboarding process.The certificate signing request is encoded text that service providers/own solution will submit it to ZATCA CA. The digital certificate will be stored in the taxpayer device/s and EGS identification data will rely on the data provided by the taxpayer through ZATCA Portal without further validation and therefore, the taxpayer is fully responsible for the accuracy and legitimacy of the data provided. Also, CSR contains the public key that will be included in the certificate, the private key is usually created at the same time that service providers/ own solution create the CSR by their selves.")+"<br><b>"+__("The CSR will be generated one and only one time!")+"</b>"
	return __(notes)

}
function getrenewalnotes(){
	let notes=__("1- ")+__("After accessing Fatoora portal, click on 'Renewing Existing Cryptographic Stamp Identifier (CSID)'.")+"<br>"+
	__("2- ")+__("Chose to generate OTP code for single EGS Unit.")+"<br>"+
	__("3- ")+__("The Fatoora Portal will generates OTP code (valid for 1 hour), copy the code in the below box.")
	return (notes)

}

function getonboardingnotes(){
	let notes=__("1- ")+__("After accessing Fatoora portal, click on 'onboard new solution unit/device'.")+"<br>"+
	__("2- ")+__("Chose to generate OTP code for single EGS Unit.")+"<br>"+
	__("3- ")+__("The Fatoora Portal will generates OTP code (valid for 1 hour), copy the code in the below box.")
	return (notes)

}

function restart(){
	let notes= __("This action will set all invoice's zatca status to 'Pending'. This action is only to be used to remove simulation actions.")+"<br>"+
	__("To continue Enter the company Name");
	return notes;

}

function csr_dialog(frm){
		if (!frm.doc.sn){
			frm.set_value("sn","1-Baha|2-version15|3-24c359bd59af")
		}
		var name=frm.doc.company_name_in_arabic || frm.doc.company_name;
		let c = new frappe.ui.Dialog({
			title: __('Enter details'),
			fields:[
				{label:__("EGS Serial Number"),description:__("1-EGS provider name |2-version  |3-Serial number"),
				fieldname:"sn",fieldtype:"Data",default:frm.doc.sn,mandatory:1,read_only:1},
				{label:__("Organization Name"),fieldname:"o",fieldtype:"Data",default:name,mandatory:1,read_only:"1"},
				{label:__("Organization Unit Name"),fieldname:"ou",fieldtype:"Data",default:frm.doc.ou,mandatory:1,description:__("Branch name for tax payers / TIN number for VAT groups.")},
				{label:__("Organization Identifier (TAX id)"),description:__("VAT Registration number, 15 digits starting and ending with 3."),
				fieldname:"uid",fieldtype:"Data",default:frm.doc.tax_id,mandatory:1},
				{label:__("Common Name"),description:__("Name or asset tracking number for the device/ EGS unit."),
				fieldname:"cn",fieldtype:"Data",default:frm.doc.cn,mandatory:1},
				{label:__("Company Email"),fieldname:"email",fieldtype:"Data",default:frm.doc.email,mandatory:1},
				{label:"",fieldname:"c",fieldtype:"Column Break"},
				{label:__("Invoice Type"),fieldname:"invoice_type",fieldtype:"Heading",default:"",mandatory:1},
				{label:__("Standard Tax Invoice"),fieldname:"t",fieldtype:"Check",default:frm.doc.t,mandatory:1},
				{label:__("Simplified Tax Invoice"),fieldname:"s",fieldtype:'Check',default:frm.doc.s,mandatory:1},
				{label:__("Buyer QR Code"),fieldname:"c",fieldtype:"Check",default:0,read_only:1},
				{label:__("Seller's QR code in self-billing"),fieldname:"z",fieldtype:"Check",default:0,read_only:1},
				{label:__("country Code"),fieldname:"cc",fieldtype:"Select",options:["SA"],default:"SA",mandatory:"1"},
				{label:__("registred Address"),description:__("Location of branch or device in 'Saudi Short Address' format from Saudi national address."),fieldname:"registredAddress",fieldtype:"Data",default:frm.doc.custom_short_address},
				{label:__("Business Category"),fieldname:"businessCategory",fieldtype:"Data",default:frm.doc.domain},
				{label:__("Restart PIH"),fieldname:"restart_pih",fieldtype:"Check",default:"1",mandatory:1,description:__("The Previous Invoice Hash is mandatory at every and each invoice.For the first invoice, the previous invoice hash is the equivalent for base64 encoded SHA256 of '0' (zero)) character.")},
			],
			size:"extra-large",
			primary_action_label:__("Generate CSR"),
			primary_action(values){
				if (!values["t"] && !values["s"]){
					frappe.show_alert({message:__("Invoice Type, you have to select at least one."),indicator:"yellow",seconds:3})
				}else{
				if (!values["ou"] || !values["cn"] || !values["registredAddress"] || !values["email"] || !values["uid"] || !values["businessCategory"]) {
					frappe.show_alert({message:__("Missing values."),indicator:"yellow",seconds:3})
				}else{
					if (values["uid"].length!=15 || values['uid'][0]!="3" || values['uid'].at(-1)!="3"){
						frappe.show_alert({message:__("Tax id must be 15 digits, begins with 3 and ends with 3."),indicator:"yellow",seconds:3})
					}else{
					if (values["registredAddress"].length!=8 || values["registredAddress"].slice(0,4).toUpperCase() != values["registredAddress"].slice(0,4) || !isNumeric(values["registredAddress"].slice(4,8)) ){
						frappe.show_alert({message:__("The short address must consists of 4 letters and 4 numbers.example : RRRD2929"),indicator:"yellow",seconds:3})
					}else{
				generate_csr(frm,values)
				c.hide();}
				}
				}
				}
			}
		})
		c.show()
	
}
function insert_csr(frm,values){
	if (values["agree"] && values["csr"]){
		frappe.call({
		doc:frm.doc,
		args:{"values":values},
		method:"insert_csr",
		freeze:true,
		freeze_message:__("Inserting CSR"),
		callback(r){
			if(r.message=="1"){
				frm.reload_doc();
			}
		}
	})
	}else{
		
	}
}

function generate_csr(frm,values){
	frappe.call({
		doc:frm.doc,
		args:{"values":values},
		method:"generate_csr",
		freeze:true,
		freeze_message:__("Generating CSR"),
		callback(r){
			if(r.message=="1"){
				
			}
		}
	})
}

function isNumeric(str) {
  if (typeof str != "string") return false // we only process strings!  
  return !isNaN(str) && // use type coercion to parse the _entirety_ of the string (`parseFloat` alone does not do this)...
         !isNaN(parseFloat(str)) // ...and ensure strings of whitespace fail
}
