from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from cryptography.hazmat.backends import default_backend
import frappe
from io import BytesIO
from frappe import _
import uuid,base64,os,requests,random
import lxml.etree as ET
from hashlib import sha256
import json
from OpenSSL import crypto
from ecdsa import SigningKey, VerifyingKey
from datetime import datetime
from cryptography import x509
from zatca.qr import qr_code
import binascii,math
from pyqrcode import create as qr_create

class CustomSalesInvoice(SalesInvoice):
	simple_invoice="assets/zatca/templates/simple_invoice.xml"
	standard_invoice="assets/zatca/templates/standard_invoice.xml"
	item_line="assets/zatca/templates/item_line.xml"
	extensions="assets/zatca/templates/extensions.xml"
	qr_code="assets/zatca/templates/qr_code.xml"
	site= frappe.local.site_path
	
	@frappe.whitelist()
	def vat_category(self):
		v=frappe.db.get_all("VAT category",filters={"default":1,"disabled":0})
		if v:
			self.custom_vat_category=v[0]["name"]
	
	def before_submit(self):
		self.zatca_status="Pending"
		ind=1
		for i in self.items:
			if ( i.is_zero_rated or i.is_exempt) and i.tax_amount>0:
				frappe.throw(_("row {} , item {} is set as zero/exempt but have tax amount >0.").format(ind,i.item_code))
			if i.tax_rate==0 and i.amount!=0:
				if not i.custom_vat_category :
					frappe.throw(_("row {} , item {} is missing vat category as it's zero taxed.").format(ind,i.item_code))
				if (not i.is_zero_rated and not i.is_exempt):
					frappe.throw(_("row {} , item {} is zero taxed, select type (zero, exempted).").format(ind,i.item_code))
				if i.is_zero_rated and i.is_exempt:
					frappe.throw(_("row {} , item {} can't be zero ated and exempted at the same time.").format(ind,i.item_code))
			ind+=1
		self.custom_pih=""
		
	
	def on_cancel(self):
		if self.simple and "Reported" in self.zatca_status:
			dont_cancel=frappe.db.get_value("Company",self.company,"do_not_cancel_reported_invoices")
			if dont_cancel:
				frappe.throw(_("You can not cancel Reported invoices. Consider creating a return/credit note."))
		if (not self.simple ) and "Cleared" in self.zatca_status:
			dont_cancel=frappe.db.get_value("Company",self.company,"do_not_cancel_cleared_invoices")
			if dont_cancel:
				frappe.throw(_("You can not cancel Cleared invoices. Consider creating a return/credit note."))
		super(CustomSalesInvoice,self).on_cancel()
		if self.ksa_einv_qr:
			file_doc=frappe.get_all("File",{"file_url":self.ksa_einv_qr})
			if len(file_doc):
				frappe.delete_doc("File",file_doc[0]["name"])
			self.ksa_einv_qr=""
		if self.xml_path:
			file_doc=frappe.get_all("File",{"file_url":self.xml_path})
			if len(file_doc):
				frappe.delete_doc("File",file_doc[0]["name"])
			self.xml_path=""			
		frappe.db.set_value("Sales Invoice",self.name,"hash","")
		frappe.db.set_value("Sales Invoice",self.name,"custom_zatca_warnings","")
		frappe.db.set_value("Sales Invoice",self.name,"zatca_status","Cancelled")
	@frappe.whitelist()
	def set_type_based_on_customer(self):
		if not self.customer:
			self.simple=0
			return
		customer_type=frappe.db.get_value("Customer",self.customer,"customer_type")
		if customer_type=="Individual":
			self.simple=1
		else:
			self.simple=0
	def on_submit(self):	
		super(CustomSalesInvoice,self).on_submit()
		company=frappe.get_doc("Company",self.company)
		if  company.custom_zatca_status!="Disabled" and company.generate_xml_on_submit:
			self.first_xml(False)
			if self.simple and company.custom_zatca_status!="Disabled" and company.report_simple_invoices_on_submit:
				self.report(show_alert=True)
			if not self.simple and  company.custom_zatca_status!="Disabled" and company.clears_standard_invoices_on_submit:
				self.clearance(show_alert=True)
		#self.save()

	@frappe.whitelist()
	def compliance(self,show_alert=False):	
		company=frappe.get_doc("Company",self.company)
		if company.custom_zatca_status=="Disabled":
			alert(_("ZATCA is disabled"),"red")
			return
		if not self.xml_path :
			frappe.throw(_("XML file not found, kindly regenerate XML."))
		if not self.hash:
			frappe.throw(_("Hash is not present in the invoice body, kindly regenerate XML."))
		if not self.uuid:
			frappe.throw(_("UUID is not present in the invoice body, kindly regenerate XML."))
		urli=get_urli(company.custom_api_endpoint)
		url=urli+"/compliance/invoices"
		f=open(self.site+self.xml_path,"r")
		xml=f.read()
		f.close()
		encoded=base64.b64encode(xml.encode("utf-8")).decode("utf-8")
		Headers = { 'accept' : 'application/json', 'Accept-Version' : company.accept_version, 'Content-Type': 'application/json', 'Accept-Language': 'en' }
		# a compliance check uses ccsid 
		auth =company.ccsid_username+":"+company.get_password("ccsid_password")
		binary_auth = auth.encode('utf-8')
		autorization_binary = base64.b64encode(binary_auth)
		autorization = autorization_binary.decode('utf-8')
		Headers["Authorization"]="Basic "+autorization
		data={"invoiceHash":self.hash,"uuid":self.uuid,"invoice":encoded}
		response = requests.post(url, data=json.dumps(data), headers=Headers)
		status_code=response.status_code
		if status_code==401:
			reporting=_("Code : 401")+"<br>"
			reporting+=_("Error") +" <b>"+_("Unauthorized")+"</b>"
			if not show_alert:
				frappe.throw(str(reporting))
		rj=response.json()
		head=""
		if len(rj["validationResults"]["infoMessages"])>0:
			head=_("Compliance Check = ")+"<span style='color:green;'>"+rj["validationResults"]["infoMessages"][0]["status"]+"</span>"
		status=""
		
		if rj["validationResults"]["warningMessages"]:
			status+="<span style='color:orange'> "+_("Warning Messages :")+"</span>"+"<br>"
			for w in rj["validationResults"]["warningMessages"]:
				status+=str(w)+"<br>"
		if rj["validationResults"]["errorMessages"]:
			status+="<span style='color:red'> "+_("Error Messages :")+"</span>"+"<br>"
			for w in rj["validationResults"]["errorMessages"]:
				status+=str(w)+"<br>"
		if rj["reportingStatus"]:
			if rj["reportingStatus"]=="REPORTED":
				status+=_("Reporting Status")+" <span style='color:green;font-weight:700;'>"+rj["reportingStatus"]+"</span>"
				status+="<br><b>"+_("This is a compliance check, Invoice is NOT actually reported to Zatca.")+"</b>"
				if not show_alert:
					frappe.msgprint(str(status),head)
				return 1
			else:
				status+=_("Reporting Status")+" <span style='color:red;font-weight:700;'>"+rj["reportingStatus"]+"</span>"
				if not show_alert:
					frappe.msgprint(str(status),head)
				return 0
		if rj["clearanceStatus"]:
			if rj["clearanceStatus"]=="CLEARED":
				status+=_("Clearance Status")+" <span style='color:green;font-weight:700;'>"+rj["clearanceStatus"]+"</span>"
				status+="<br><b>"+_("This is a compliance check, Invoice is NOT actually cleared to Zatca.")+"</b>"
				if not show_alert:
					frappe.msgprint(str(status),head)
				return 1	
			else:
				status+=_("Clearance Status")+" <span style='color:red;font-weight:700;'>"+rj["clearanceStatus"]+"</span>"
				if not show_alert:
					frappe.msgprint(str(status),head)
				return 0
		if not show_alert:
			frappe.msgprint(str(status),head)
				
	@frappe.whitelist()
	def clearance(self,show_alert=False):
		company=frappe.get_doc("Company",self.company)
		if company.custom_zatca_status=="Disabled":
			alert(_("ZATCA is disabled"),"red")
			return
		if company.custom_zatca_status=="Compliance Check":
			frappe.msgprint(_("Zatca is running compliance checks, finish onboarding before clearing invoices."))
			return
		if self.simple:
			frappe.throw(_("You can not clear a simple invoice."))
		if not self.xml_path :
			frappe.throw(_("XML file not found, kindly regenerate XML."))
		if not self.hash:
			frappe.throw(_("Hash is not present in the invoice body, kindly regenerate XML."))
		if not self.uuid:
			frappe.throw(_("UUID is not present in the invoice body, kindly regenerate XML."))
		f=open(self.site+self.xml_path,"r")
		xml=f.read()
		f.close()
		encoded=base64.b64encode(xml.encode("utf-8")).decode("utf-8")
		urli=get_urli(company.custom_api_endpoint)
		url=urli+"/invoices/clearance/single"
		Headers = { 'accept' : 'application/json', 'Clearance-Status': '1', 'Accept-Version' : company.accept_version, 'Content-Type': 'application/json', 'Accept-Language': 'en' }
		if company.custom_zatca_status=="Compliance Check":
			auth =company.ccsid_username+":"+company.get_password("ccsid_password")
		else:
			auth =company.pcsid_username+":"+company.get_password("pcsid_password")
		binary_auth = auth.encode('utf-8')
		autorization_binary = base64.b64encode(binary_auth)
		autorization = autorization_binary.decode('utf-8')
		Headers["Authorization"]="Basic "+autorization
		data={"invoiceHash":self.hash,"uuid":self.uuid,"invoice":encoded}
		response = requests.post(url, data=json.dumps(data), headers=Headers)
		status_code=response.status_code
		if status_code==401:
			reporting=_("Reporting Status = ")+"<span style='color:red;'>"+_("NOT_CLEARED")+"</span><br>"
			reporting+=_("Code : 401")+"<br>"
			reporting+=_("Error") +" <b>"+_("Unauthorized")+"</b>"
			if not show_alert:
				frappe.throw(str(reporting))
		rj=response.json()
		############################################################ REJECTED #################################################################
		if status_code!=200 and status_code!=202:
			error=""
			reporting=_("Reporting Status = ")+"<span style='color:red;'>"+_(rj["clearanceStatus"])+"</span><br>"
			reporting=""
			for i in rj["validationResults"]["errorMessages"]:
				reporting+="- "+"<b>"+_(i["code"])+", "+_(i["category"])+"</b> :"
				reporting+=_(str(i["message"]))+"<br>"
				error+="<b style='color:darkred'>"+_(str(i["message"]))+"</b><br>"
			self.custom_zatca_warnings=error
			self.zatca_status="Rejected"
			frappe.db.set_value("Sales Invoice",self.name,"custom_zatca_warnings",error)
			frappe.db.set_value("Sales Invoice",self.name,"zatca_status","Rejected")
			#self.save(ignore_version=True)
			if not show_alert:
				frappe.msgprint(
					title="<span style='color:red;font-weight:700;'>"+_("NOT CLEARED")+"</span>",
					raise_exception=False,
					msg=reporting
				)
			com=_("Fail to clear invoice to ZATCA")+_("Datetime")+": <span style='font-weight:700;'>"+str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))+"</span><br>"
			com+=error
			comment(self.name,com)
			return False
		else:
			msg=_("Invoice Cleared to zakat tax and customs authority.")+"<br>"
			###################################################### CLEARED with WARNINGS
			if status_code==202:
				warnings=""
				msg+="<span style='font-weight:700;;font-weight:400'>"+_("Warnings")+":</span><br>"
				for i in rj["validationResults"]["warningMessages"]:
					msg+="- "+"<b>"+_(i["code"])+", "+_(i["category"])+"</b> :"
					msg+=_(str(i["message"]))+"<br>"
					warnings+="<b>"+_(str(i["message"]))+"</b><br>"
				self.zatca_status="Cleared with warnings"
				self.custom_zatca_warnings=warnings
				frappe.db.set_value("Sales Invoice",self.name,"custom_zatca_warnings",warnings)
				frappe.db.set_value("Sales Invoice",self.name,"zatca_status","Cleared with warnings")
				com=_("Invoice cleared to ZATCA with warnings.")+_("Datetime")+": <span style='font-weight:700;'>"+str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))+"</span><br>"
				com+=warnings
				comment(self.name,com)
			######################################################### CLEARED ##################################################
			else:
					
				self.custom_zatca_warnings=""
				frappe.db.set_value("Sales Invoice",self.name,"custom_zatca_warnings","")
				comment(self.name,_("Invoice cleared to ZATCA.")+_("Datetime")+": <span style='font-weight:700;'>"+str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))+"</span>")
				self.zatca_status="Cleared"
				frappe.db.set_value("Sales Invoice",self.name,"zatca_status","Cleared")
			self.custom_clearing_to_zatka_time=frappe.utils.now()
			frappe.db.set_value("Sales Invoice",self.name,"custom_clearing_to_zatka_time",frappe.utils.now())
			if show_alert:
				alert(_("Invoice Cleared to zakat tax and customs authority."))
			else:
				frappe.msgprint(
					title="<span style='color:green;font-weight:700;'>"+_("CLEARED")+"</span>",
					raise_exception=False,
					msg=msg
			);
			invoice=rj["clearedInvoice"]
			invoice=base64.b64decode(invoice).decode("utf-8")
			f=open(self.site+self.xml_path,"w")
			f.write(invoice)
			f.close()
			qr_code=invoice.split("<cbc:ID>QR</cbc:ID>")[1]
			qr_code=qr_code.split("""mimeCode="text/plain">""")[1]
			qr_code=qr_code.split("<")[0]
			if ">" in qr_code or "<" in qr_code or "\"" in qr_code:
				alert("Error fetching QR Code from Cleared Invoice")
			if self.ksa_einv_qr:
				file_doc=frappe.get_all("File",{"file_url":self.ksa_einv_qr})
				if len(file_doc):
					frappe.delete_doc("File",file_doc[0]["name"])
			qr_image=BytesIO()
			url=qr_create(qr_code,error="L")
			url.png(qr_image,scale=2,quiet_zone=1)
			name=self.xml_path.split("/")[-1].replace("xml","png")
			_file=frappe.get_doc({
				"doctype":"File",
				"file_name":name,
				"is_private":0,
				"content":qr_image.getvalue(),
				"attached_to_doctype":"Sales Invoice",
				"attached_to_name":self.name
			})
			_file.save()
			frappe.db.set_value("Sales Invoice",self.name,"ksa_einv_qr",_file.file_url)
			frappe.db.set_value("Sales Invoice",self.name,"qr_code_text",qr_code)
			self.ksa_einv_qr=_file.file_url
			self.qr_code_text=qr_code
			#self.save(ignore_version=True)
			return(True)
		return (False)


	@frappe.whitelist()
	def report(self,show_alert=False):
		if not self.xml_path:
			return
		company=frappe.get_doc("Company",self.company)
		if company.custom_zatca_status=="Disabled":
			alert(_("ZATCA is disabled"),"red")
			return
		if company.custom_zatca_status=="Compliance Check":
			frappe.msgprint(_("Zatca is running compliance checks, finish onboarding before reporting invoices."))
			return
		d=frappe.utils.get_datetime(str(self.posting_date)+" "+str(self.posting_time))
		if d > frappe.utils.get_datetime():
			if not show_alert:
				frappe.msgprint(_("Invoice issue date must be less or equal to the current datetime."),_("Posting time Error"),"orange")
				return False
		difference=(frappe.utils.get_datetime()-d)
		if 0 and difference.days>0:
			frappe.throw(_("You can't report simplified invoices after 24hours from the time of generation. You have to correct the invoice with ZATCA within 15th of the next month."))	
		f=open(self.site+self.xml_path,"r")
		xml=f.read()
		f.close()
		encoded=base64.b64encode(xml.encode("utf-8"))
		encoded=encoded.decode("utf-8")
		urli=get_urli(company.custom_api_endpoint)
		url=urli+"/invoices/reporting/single"
		Headers = { 'accept' : 'application/json', 'Clearance-Status': '1', 'Accept-Version' : company.accept_version, 'Content-Type': 'application/json', 'Accept-Language': 'en' }
		auth =company.pcsid_username+":"+company.get_password("pcsid_password")
		binary_auth = auth.encode('utf-8')
		autorization_binary = base64.b64encode(binary_auth)
		autorization = autorization_binary.decode('utf-8')
		Headers["Authorization"]="Basic "+autorization
		data={"invoiceHash":self.hash,"uuid":self.uuid,"invoice":encoded}
		response = requests.post(url, data=json.dumps(data), headers=Headers)
		status_code=response.status_code
		if status_code==401:
			reporting=_("Reporting Status = ")+"<span style='color:red;'>"+_("NOT REPORTED")+"</span><br>"
			reporting+=_("Code : 401")+"<br>"
			reporting+=_("Error") +" <b>"+_("Unauthorized")+"</b>"
			if not show_alert:
				frappe.throw(reporting)
		rj=response.json()
		################################################# REJECTED #############################################################
		if status_code!=200 and status_code!=202 :
			reporting=_("Reporting Status = ")+"<span style='color:red;'>"+_(rj["reportingStatus"])+"</span><br>"
			reporting=""
			error=""
			just_production=False
			for i in rj["validationResults"]["errorMessages"]:
				reporting+="- "+"<b>"+_(i["code"])+", "+_(i["category"])+"</b> :"
				reporting+="<b>"+_(str(i["message"]))+"</b><br>"
				if "User only allowed to use the vat number that exists in the authentication certificate" in str(i["message"]):
					just_production=True
				error+="<b style='color:darkred'>"+_(str(i["message"]))+"</b><br>"
			if just_production:
				reporting+="<b style='color:darkred;font-weight:700'>"+_("If you just switched to production mode, Kindly regenerate XML.")+"</b>"
				error+="<b style='color:darkred;font-weight:700'>"+_("If you just switched to production mode, Kindly regenerate XML.")+"</b>"
			self.custom_zatca_warnings=error
			self.zatca_status="Rejected"
			frappe.db.set_value("Sales Invoice",self.name,"custom_zatca_warnings",error)
			frappe.db.set_value("Sales Invoice",self.name,"zatca_status","Rejected")
			#self.save(ignore_version=True)
			if not show_alert:
				frappe.msgprint(
					title="<span style='color:red;font-weight:700;'>"+_("NOT REPORTED")+"</span>",
					raise_exception=False,
					msg=reporting
				)
			com=_("Fail to report invoice to ZATCA")+_("Datetime")+": <span style='font-weight:700;'>"+str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))+"</span><br>"
			com+=error
			comment(self.name,com)
			return False
		else:
			msg=_("Invoice Reported to zakat tax and customs authority.")+"<br>"
			####################################### REPORTED with WARNINGS  ###################################################
			if status_code==202:
				warnings=""
				msg+="<span style='font-weight:700;;font-weight:400'>"+_("Warnings")+"</span>"
				for i in rj["validationResults"]["warningMessages"]:
					msg+="- "+"<b>"+_(i["code"])+", "+_(i["category"])+"</b> :"
					msg+=_(str(i["message"]))+"<br>"
					warnings+=_(str(i["message"]))+"<br>"
				self.zatca_status="Reported with warnings"
				self.custom_zatca_warnings=warnings
				frappe.db.set_value("Sales Invoice",self.name,"custom_zatca_warnings",warnings)
				frappe.db.set_value("Sales Invoice",self.name,"zatca_status","Reported with warnings")
				com=_("Invoice reported to ZATCA with warnings.")+_("Datetime")+": <span style='font-weight:700;'>"+str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))+"</span><br>"
				com+=warnings
				comment(self.name,com)
			###################################### REPORTED ###################################################################
			else:
				self.custom_zatca_warnings=""
				self.zatca_status="Reported"
				frappe.db.set_value("Sales Invoice",self.name,"custom_zatca_warnings","")
				frappe.db.set_value("Sales Invoice",self.name,"zatca_status","Reported")
				comment(self.name,_("Invoice reported to ZATCA.")+_("Datetime")+": <span style='font-weight:700;'>"+str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))+"</span>")
			if show_alert:
				alert(_("Invoice Reported to zakat tax and customs authority."))
			else:
				frappe.msgprint(
				title="<span style='color:green;font-weight:700;'>"+_("REPORTED")+"</span>",
				raise_exception=False,
				msg=msg
				)
			self.custom_reporting_to_zatka_time=frappe.utils.now()
			frappe.db.set_value("Sales Invoice",self.name,"custom_reporting_to_zatka_time",frappe.utils.now())
			#self.save(ignore_version=True)
			return True
		return 


	@frappe.whitelist()
	def first_xml(self,show_alert=True):
		company=frappe.get_doc("Company",self.company)
		if company.custom_zatca_status=="Disabled":
			alert(_("ZATCA is disabled"),"red")
			return
		if not self.uuid:
			self.uuid=str(uuid.uuid4())
			frappe.db.set_value("Sales Invoice",self.name,"uuid",self.uuid)
		possible_warnings=False
		if self.simple:
			f=open(self.simple_invoice,"r")
			type_code_name="0200000"
		else:
			customer_tax_id,customer_address=self.validate_customer_details()
			f=open(self.standard_invoice,"r")
			type_code_name="0100000"
			if not customer_address or not customer_tax_id:
				possible_warnings=True
		xml=f.read()
		if not self.uuid:
			self.uuid=str(uuid.uuid4())
		links=frappe.db.get_all("Dynamic Link",filters={"link_doctype":"Company","link_name":self.company,"parenttype":"Address"},fields=["parent"])
		if len(links)>0:
			address=frappe.get_doc("Address",links[0]["parent"])
		else:
			frappe.throw(_("Address is missing for company {}").format(self.company))
		qr_code=""
		payment_means="10"
		country_code="SA"
		type_code="388"
		debit_credit_reason=""
		billing_reference=""
		delivery_date="""<cac:Delivery>
    	<cbc:ActualDeliveryDate>{0}</cbc:ActualDeliveryDate>
    </cac:Delivery>""".format(self.posting_date)
		if self.is_return or self.is_debit_note:
			delivery_date=""
			if self.is_return:
				type_code="381"
			else:
				type_code="383"
				
			debit_credit_reason="<cbc:InstructionNote>"+self.custom_reason+"</cbc:InstructionNote>" if self.custom_reason else  "<cbc:InstructionNote>CANCELLATION_OR_TERMINATION</cbc:InstructionNote>"
			billing_reference="""
			<cac:BillingReference>
				<cac:InvoiceDocumentReference>
					<cbc:ID>{}</cbc:ID>
				</cac:InvoiceDocumentReference>
			</cac:BillingReference>
			""".format(self.return_against)
		crn=company.cr_number
		scheme_type="CRN"
		schemes={"Commercial Registration number":"CRN","MOMRAH license":"MOM","MHRSD license":"MLS","700 Number":"700","MISA license":"SAG","Other OD":"OTH"}
		if company.custom_scheme:
			scheme_type=schemes[company.custom_scheme]
		try:
			seconds=self.posting_time.seconds
		except:
			seconds=frappe.utils.get_timedelta(self.posting_time).seconds
		h=str(seconds//3600)
		h="0"+h if len(h) ==1 else h
		m=str((seconds%3600)//60)
		m="0"+m if len(m) ==1 else m
		s=str((seconds%3600)%60)
		s="0"+s if len(s) ==1 else s
		issue_time=h+":"+m+":"+s
		tax_id=company.tax_id
		taxable=0
		subtax="""<cac:TaxSubtotal>
            <cbc:TaxableAmount currencyID="{currency}">{taxable_amount_}</cbc:TaxableAmount>
            <cbc:TaxAmount currencyID="{currency}">{tax_amount}</cbc:TaxAmount>
             <cac:TaxCategory>
                 <cbc:ID >{tax_category}</cbc:ID>
                 <cbc:Percent>{vat_percent}</cbc:Percent>
                 {tax_code}
            	 {tax_reason}
                <cac:TaxScheme>
                   <cbc:ID >VAT</cbc:ID>
                </cac:TaxScheme>
             </cac:TaxCategory>
        </cac:TaxSubtotal>""".replace("{currency}",self.currency)
		tax15=0
		taxes15=0
		taxzero=0
		subtaxes=""
		zero=0
		zerocode=""
		exempt=0
		exemptcode=""
		total_before_vat=0
		total_vat=0
		have_zero=False
		have_exempt=False
		for i in self.items:
			if i.tax_amount!=0:
				taxable+=i.amount
			if i.tax_rate==15:
				tax15+=i.net_amount
				taxes15+=i.tax_amount
			if i.tax_amount==0 :
				if i.is_zero_rated :
					have_zero=True
					zero+=i.net_amount
					zerocode=i.custom_vat_category
				if i.is_exempt:
					have_exempt=True
					exemptcode=i.custom_vat_category
					exempt+=i.net_amount
		if tax15 or (not have_zero and not have_exempt):
			new=subtax.replace("{tax_category}","S").replace("{vat_percent}","15.00").replace("{taxable_amount_}",num(tax15)).replace("{tax_amount}",num(taxes15)).replace("{tax_code}","").replace("{tax_reason}","")
			subtaxes+=new
			
			total_before_vat+=truncate(tax15)
			#total_vat+=truncate(tax15*0.15)
			
		codes={"E":exempt,"Z":zero}
		for tax_category in codes:
			if tax_category=="E" and not have_exempt:
				continue
			if tax_category=="Z" and not have_zero:
				continue
			total_before_vat+=round(codes[tax_category],2)
			t=zerocode if tax_category=="Z" else exemptcode
			tax_code="<cbc:TaxExemptionReasonCode>"+str(t)+"</cbc:TaxExemptionReasonCode>"
			text=frappe.db.get_value("VAT category",t,"english_text")
			tax_reason="<cbc:TaxExemptionReason>"+str(text)+"</cbc:TaxExemptionReason>"
			
			new=subtax.replace("{tax_category}",tax_category).replace("{vat_percent}","0.00").replace("{taxable_amount_}",num(codes[tax_category]))
			new=new.replace("{tax_amount}","0.00").replace("{tax_code}",tax_code).replace("{tax_reason}",tax_reason)
			subtaxes+=new
		if self.custom_pih and self.custom_pih !="":
			pih=self.custom_pih
		else:
			pih=company.pih
		outstanding_total=self.rounded_total if self.rounded_total else self.total
		
		lines,total_before_vat,total_vat=self.get_lines()
		
		#
		total_after_vat=round(total_before_vat+total_vat,2)
		base_vat=num(total_vat*self.conversion_rate)
		#frappe.throw(str(total_after_vat))
		replace={"{id}":self.name,"{uuid}":self.uuid,"{issue_date}":self.posting_date,"{issue_time}":issue_time,"{currency}":self.currency,
			"{pih}":pih,"{tax_currency}":"SAR","{qr_code}":qr_code,"{company_tax_id}":tax_id,"{company_name}":company.name,
			"{vat_percent}":num(self.items[0].tax_rate),"{total}":num(total_before_vat),"{total_discount}":num(0),"{tax_amount}":num(total_vat),
			"{taxable_amount}":num(total_before_vat),"{total_amount}":num(total_after_vat),"{total_advance}":num(0),
			"{payable_amount}":num(total_after_vat),"{payment_means}":payment_means,"{base_tax_amount}":base_vat,
			"{country_code}":country_code,"{scheme_type}":scheme_type,"{scheme_id}":crn,
			"{street_name}":address.address_line1,"{city_name}":address.city,"{postal_code}":address.pincode,"{building_number}":address.building_number,
			"{city_subdivision}":address.subdivision,"{plot}":address.plot,"{debit_credit_reason}":debit_credit_reason,
			"{billing_reference}":billing_reference,"{customer_name}":self.customer,"{delivery_date}":delivery_date,"{subtax}":subtaxes,"{rounding_amount}":round(0,2)
}		
		replace["{customer_scheme_id}"]= ""
		replace["{customer_id}"]=""
		replace["{customer_street_name}"]=address.address_line1 or ""
		replace["{customer_scheme}\n"]=""
		if not self.simple:
			replace["{customer_tax_id}"]=customer_tax_id or ''
			replace["{customer_street_name}"]=customer_address.address_line1 if customer_address else ""
			replace["{customer_building_number}"]=customer_address.building_number if customer_address else ""
			replace["{customer_plot}"]=customer_address.plot if customer_address else ""
			replace["{customer_city_subdivision}"]=customer_address.subdivision if customer_address else ""
			replace["{customer_city_name}"]=customer_address.city if customer_address else ""
			replace["{customer_postal_code}"]=customer_address.pincode if customer_address else ""
			if customer_address:
				a=customer_address
				possible_warnings= not a.address_line1 or not a.plot or not a.pincode or not a.subdivision or not a.city or not a.building_number
		replace["{type_code_name}"]=type_code_name
		replace["{type_code}"]=type_code
		xml=xml.replace("{invoice_lines}",lines)
		xml=replaceAll(xml,replace)
		print(20*"--")
		print(total_before_vat,total_vat)
		
		if not self.simple:
			xml=xml.replace("{ext:UBLExtensions}","")
			xml=xml.replace("{QR}","")
		time=str(self.posting_time).replace(":","")[0:6]
		if time[-1]==".":
			time=time[:-2]+"0"+time[-2]
		new_name=company.tax_id+"_"+str(self.posting_date).replace("-","")+"T"+time+"_"+self.name+".xml"
		if self.simple:
			self.validate_signature()
			xml=self.sign_invoice(company,xml,total_after_vat,float(base_vat))
			
			if not xml:
				self.xml_path=""
				alert("Error while Signing xml invoice.","red")
				return(False)
		if xml:
			if not self.xml_path:
				file_=frappe.get_doc({
					"doctype":"File",
					"is_private":1,
					"attached_to_doctype":"Sales Invoice",
					"attached_to_name":self.name,
					"file_name":new_name,
					"content":xml.encode("utf-8")		
				})
				file_.save()
				self.xml_path=file_.file_url
				frappe.db.set_value("Sales Invoice",self.name,"xml_path",file_.file_url)
			else:
				new_file=open(self.site+self.xml_path,"w")
				new_file.write(xml)
				new_file.close()
			if self.simple:
				
				if self.ksa_einv_qr:
					file_doc=frappe.get_all("File",{"file_url":self.ksa_einv_qr})
					if len(file_doc):
						frappe.delete_doc("File",file_doc[0]["name"])
				qr_image=BytesIO()
				url=qr_create(self.qr_code_text,error="L")
				url.png(qr_image,scale=2,quiet_zone=1)
				name=self.xml_path.split("/")[-1].replace("xml","png")
				_file=frappe.get_doc({
					"doctype":"File",
					"file_name":name,
					"is_private":0,
					"content":qr_image.getvalue(),
					"attached_to_doctype":"Sales Invoice",
					"attached_to_name":self.name
				})
				_file.save()
				self.ksa_einv_qr=_file.file_url
				frappe.db.set_value("Sales Invoice",self.name,"ksa_einv_qr",_file.file_url)
				#frappe.db.set_value("Sales Invoice",self.name,"qr_code_text",qr_code)
				#self.qr_code_text=qr_code
		if not self.simple:
			cananolized_xml=cananolize(self.site+self.xml_path)
			if not cananolized_xml:
				alert("Error while canonicalizing xml invoice.","red")
				return(False)
			hash_=get_hash(cananolized_xml)
			self.hash=hash_
			frappe.db.set_value("Sales Invoice",self.name,"hash",hash_)
			if show_alert:
				alert(_("Standard Invoice XML Created successfully."))
		if not self.custom_pih:
			self.custom_pih=pih
			frappe.db.set_value("Sales Invoice",self.name,"custom_pih",pih)
			frappe.db.set_value("Company",company.name,"pih",self.hash,update_modified=False)
		#self.save(ignore_version=True)
		comment(self.name,_("XML Created successfully."))
		if possible_warnings:
			alert(_("Possible warnings on Report/Clearance!"),"orange")
		return(True)

	def get_lines(self,tax_category="S"):
		result=""
		f=open(self.item_line,"r")
		temp=f.read()
		item_id=1
		total_before_vat=0
		vat=0
		for i in self.items:
			grand_total=i.total_amount or i.net_amount
			tax=truncate(i.net_amount*i.tax_rate/100)
			tax=i.tax_amount
			
			#frappe.throw(str([tax,i.net_amount,num(tax+i.net_amount)]))
			item_name="".join(e for e in i.item_name if (e.isalnum() or e==" "))
			r=replaceAll(temp,{"{item_id}":item_id,"{qty}":num(i.qty),"{total}":num(i.net_amount),"{tax_amount}":num(tax),
			"{grand_total}":num(round(i.net_amount+tax,2)),"{discount}":num(0),
			"{item_name}":item_name,"{rate}":num(i.net_rate)
			})
			total_before_vat+=float(num((i.net_amount)))
			vat+=tax
			if i.is_exempt:
				r=r.replace("{tax_category}","E")
				r=r.replace("{tax_percentage}","0.0")
			elif i.is_zero_rated:
				r=r.replace("{tax_category}","Z")
				r=r.replace("{tax_percentage}","0.0")
			else:
				r=r.replace("{tax_category}","S")
				r=r.replace("{tax_percentage}",num(i.tax_rate))
			result+=r
			item_id+=1
		if result[-1]=="\n":
			result=result[:-1]
		return result, total_before_vat,vat
	def sign_invoice(self,company,xml,total_after_vat,total_vat):
		#Signing Process - 
		
		if not xml:
		
			alert("Error : XML file not found","red")
			return False
		#Step 1: Generate Invoice Hash
		#remove extensions, qr and signature
		xml_=xml
		xml_=replaceAll(xml,{"    {ext:UBLExtensions}\n":"","    {QR}\n":"","{cac:signature}":""})
		randname="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))
		hf=open(randname+".xml","w")
		hf.write(xml_)
		hf.close()
		#Canonicalize the Invoice using the C14N11 standard
		cananolized_xml= cananolize(randname+".xml")
		if not cananolized_xml:
			alert("Error while canonicalizing xml invoice.","red")
			return(False)
		hf=open(randname+".xml","w")
		hf.write(cananolized_xml)
		hf.close()
		os.remove(randname+".xml")
		xml_sha256=sha256(cananolized_xml.encode('utf-8')).hexdigest()
		hash_=base64.b64encode(bytes.fromhex(xml_sha256)).decode()         #  <<<<  this is the invoice hash
		self.hash=hash_
		frappe.db.set_value("Sales Invoice",self.name,"hash",hash_)
		pkey=frappe.db.get_value("Company",self.company,"private_key")
		if not pkey or pkey=="":
			alert(_("ZATCA: Private key not found"),"red")
			return(False)
		if "-----BEGIN EC PRIVATE KEY-----" not in pkey:
			pkey="-----BEGIN EC PRIVATE KEY-----\n"+pkey+"\n-----END EC PRIVATE KEY-----"
		f=open(randname+"hash.txt","wb+")
		f.write(base64.b64decode(hash_))
		f.close()
		f=open(randname+"key.pem","wb+")
		f.write(pkey.encode())
		f.close()
		sig=os.popen("openssl dgst -sha256 -sign "+randname+"key.pem "+randname+"hash.txt | base64 /dev/stdin").read()
		signature=str(sig).replace(" ","").replace("\n","")
		os.remove(randname+"key.pem")
		os.remove(randname+"hash.txt")
		#Step 3: Generate Certificate Hash
		try:
			certificate=get_certificate(self.company)
			certificate_sha256=sha256(certificate.encode('utf-8')).hexdigest()
			certificate_hash=base64.b64encode(certificate_sha256.encode("utf-8")).decode("utf-8")
		except:
			alert("ZATCA: Certificate Decode Issue: Error hashing Certificate.","red")
			return(False)
		#Step 4: Populate the Signed Properties Output
		sign_time=str(datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
		tmp_certificate = "-----BEGIN CERTIFICATE-----\n" + certificate + "\n-----END CERTIFICATE-----"
		try:
			cert = x509.load_pem_x509_certificate(tmp_certificate.encode(), default_backend())
			serial_number=cert.serial_number
			cert_issuer = ''
			for x in range(len(cert.issuer.rdns) - 1, -1, -1):
				cert_issuer += cert.issuer.rdns[x].rfc4514_string() + ", "
			cert_issuer = cert_issuer[:-2]
		except:
			alert("ZATCA: Certificate Decode Issue: Error decoding Certificate.","red")
			return(False)
		#step5:
		signed_properties=""
		serial_number=str(serial_number)
		cet_isser=str(cert_issuer)
		signature_certificate_for_hash ='''<xades:SignedProperties xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" Id="xadesSignedProperties">\n                                    <xades:SignedSignatureProperties>\n                                        <xades:SigningTime>'''+sign_time+'''</xades:SigningTime>\n                                        <xades:SigningCertificate>\n                                            <xades:Cert>\n                                                <xades:CertDigest>\n                                                    <ds:DigestMethod xmlns:ds="http://www.w3.org/2000/09/xmldsig#" Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>\n                                                    <ds:DigestValue xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'''+str(certificate_hash) +'''</ds:DigestValue>\n                                                </xades:CertDigest>\n                                                <xades:IssuerSerial>\n                                                    <ds:X509IssuerName xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'''+cert_issuer+'''</ds:X509IssuerName>\n                                                    <ds:X509SerialNumber xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'''+serial_number+'''</ds:X509SerialNumber>\n                                                </xades:IssuerSerial>\n                                            </xades:Cert>\n                                        </xades:SigningCertificate>\n                                    </xades:SignedSignatureProperties>\n                                </xades:SignedProperties>'''
		sha_256_5 = sha256()
		sha_256_5.update(signature_certificate_for_hash.encode())
		signed_properties= base64.b64encode(sha_256_5.hexdigest().encode()).decode('UTF-8')
		replace={"{hash}":hash_,"{signature}":signature,"{certificate}":certificate,"{certificate_hash}":certificate_hash,
		"{signing_time}":sign_time,"{issue_name}":cert_issuer,"{serial_number}":serial_number,
		"{signed_properties}":signed_properties
		}
		extensions=read(self.extensions)
		extensions=replaceAll(extensions,replace)
		qr=read(self.qr_code)
		qr=qr.replace("</cac:Signature>\n","</cac:Signature>")
		tax_id=frappe.db.get_value("Company",self.company,"tax_id")
		#ECDSA signature of the cryptographic stamp tag-9
		public_key,tagnine=company.custom_cet_public_key,company.custom_cert_sig_algo
		if not public_key or not tagnine:
			public_key,tagnine=tag_nine(self.company)
			if not tagnine or not public_key:
				alert("ZATCA: Certificate Decode Issue: Error decoding Certificate.","red")
				return (False)
		try:
			seconds=frappe.utils.get_timedelta(self.posting_time).seconds
		except:
			seconds=self.posting_time.seconds
		h=str(seconds//3600)
		h="0"+h if len(h) ==1 else h
		m=str((seconds%3600)//60)
		m="0"+m if len(m) ==1 else m
		s=str((seconds%3600)%60)
		s="0"+s if len(s) ==1 else s
		issue_time=h+":"+m+":"+s
		timestamp=str(self.posting_date)+"T"+issue_time #+"Z"
		#############################################################   making QR code ##############
		
		qr_str=qr_code(self.company,tax_id,timestamp,num(total_after_vat),num(total_vat),hash_,signature,public_key,tagnine)
		#qr_str=str(qr_code.base64)
		self.qr_code_text=qr_str
		frappe.db.set_value("Sales Invoice",self.name,"qr_code_text",qr_str)
		qr=qr.replace("{qr_code}",qr_str)
		xml=xml.replace("\n    {ext:UBLExtensions}\n",extensions)
		xml=xml.replace("{QR}\n    ",qr)
		#self.save(ignore_version=True)
		alert(_("Invoice signed successfully"))
		return(xml)
	def validate_customer_details(self):
		customer_tax_id=frappe.db.get_value("Customer",self.customer,"tax_id")
		if self.customer_address:
			address=frappe.get_doc("Address",self.customer_address)
			return customer_tax_id,address
		else:
			return customer_tax_id,None
	def validate_signature(self):
		certificate=get_certificate(self.company)
		if not certificate:
			frappe.throw(_("Certificate not Found, kindly regenerate credentials."))
		return


def replaceAll(txt,d):
	tmp_txt=txt
	for i in d:
		tmp_txt=tmp_txt.replace(i,str(d[i]))
	return(tmp_txt)
#Canonicalize the Invoice using the C14N11 standard,return string
def cananolize(xml_path):
	try:
		rando="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))
		et = ET.parse(xml_path)
		et.write_c14n(rando+".xml",exclusive=0, with_comments=0)
		f=open(rando+".xml","r")
		cananolized_xml=f.read()
		f.close()
		os.remove(rando+".xml")
		return(cananolized_xml)
	except:
		return(None)
#hash the xml string using SHA-256 , then encode using HEX-to Base64 Encoder
def get_hash(xml):
	xml_sha256=sha256(xml.encode('utf-8')).hexdigest()
	hash=base64.b64encode(bytes.fromhex(xml_sha256)).decode()
	return hash
def read(file):
	try:
		f=open(file,"r")
		msg=f.read()
		f.close()
		return(msg)
	except:
		return(None)
def get_certificate(company):
	pcsid=frappe.db.get_value("Company",company,"pcsid_username")   # <<<< Production csid = certificate 
	if pcsid:
		cert=base64.b64decode(pcsid.encode("utf-8")).decode()
		cert=cert.replace("-----BEGIN CERTIFICATE-----","")
		cert=cert.replace("-----END CERTIFICATE-----","")
		cert=cert.replace("\n","")
		cert=cert.replace("\t","")
		return(cert)
	else:
		ccsid=frappe.db.get_value("Company",company,"ccsid_username")   # <<<< compliance csid = certificate for compliance checks
		if ccsid:
			cert=base64.b64decode(ccsid.encode("utf-8")).decode()
			cert=cert.replace("-----BEGIN CERTIFICATE-----","")
			cert=cert.replace("-----END CERTIFICATE-----","")
			cert=cert.replace("\n","")
			cert=cert.replace("\t","")
		return(cert)
	return(None)
def tag_nine(company):
	#return public key and signature algorithm of a certificate
	rand="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))   #certificate will stored in a random file in /tmp to avoid certificate collision
	#certificate = x509.load_pem_x509_certificate(cert.encode(), default_backend())
	pcsid=frappe.db.get_value("Company",company,"pcsid_username")
	if not pcsid:
		pcsid=frappe.db.get_value("Company",company,"ccsid_username")
	certificate=base64.b64decode(pcsid.encode("utf-8")).decode()
	if "-----BEGIN CERTIFICATE-----\n" not in certificate:
		certificate = "-----BEGIN CERTIFICATE-----\n" + certificate + "\n-----END CERTIFICATE-----"
	f=open("/tmp/"+rand+".pem","w+")
	f.write(certificate)
	f.close()
	certificate_public_key = "openssl x509 -pubkey -noout -in /tmp/"+rand+".pem"
	#get public key
	zatca_cert_public_key = os.popen(certificate_public_key).read()
	zatca_cert_public_key = zatca_cert_public_key.replace('-----BEGIN PUBLIC KEY-----', '')\
								.replace('-----END PUBLIC KEY-----', '')\
								 .replace('\n', '').replace(' ', '')
	os_cmd="openssl x509 -in /tmp/"+rand+".pem -text -noout"
	cert=os.popen(os_cmd).read()
	cert_find = cert.rfind("Signature Algorithm: ecdsa-with-SHA256")
	#getting signature algorith
	if cert_find > 0 and cert_find + 38 < len(cert):
		cert_sig_algo = cert[cert.rfind("Signature Algorithm: ecdsa-with-SHA256") + 38:].replace('\n', '')\
		.replace(':', '')\
		.replace(' ', '')
		return(zatca_cert_public_key,cert_sig_algo.replace("SignatureValue",""))
	else:
		return(None,None)
def clear_report_invoices():
	#clear all pending / rejected invoices
	comp=frappe.db.get_all("Company",filters={"custom_zatca_status":"Enabled","custom_auto_report":"Daily"})
	comp=[i["name"] for i in comp]
	invoices=frappe.db.get_all("Sales Invoice",filters=[["company",'in',comp],["docstatus","in",["1"]],["zatca_status","in",["Pending","Rejected"]]],fields=["name","company"])
	for i in invoices:
		doc=frappe.get_doc("Sales Invoice",i["name"])
		try:
			if not doc.xml_path:
				doc.first_xml(True)
			if doc.simple:
				doc.report(True)
			else:
				doc.clearance(True)
		except:
			continue
def clear_report_invoices_hourly():
	comp=frappe.db.get_all("Company",filters={"custom_zatca_status":"Enabled","custom_auto_report":"Hourly"})
	comp=[i["name"] for i in comp]
	invoices=frappe.db.get_all("Sales Invoice",filters=[["company",'in',comp],["docstatus","in",["1"]],["zatca_status","in",["Pending","Rejected"]]],fields=["name","company"])
	for i in invoices:
		doc=frappe.get_doc("Sales Invoice",i["name"])
		try:
			if not doc.xml_path:
				doc.first_xml(True)
			if doc.simple:
				doc.report(True)
			else:
				doc.clearance(True)
		except:
			print("error"+str(i["name"]))
			continue
@frappe.whitelist()
def set_overdue():
	return
@frappe.whitelist()
def report_all(items=None):
	comp=frappe.db.get_all("Company",filters={"custom_zatca_status":"Enabled"})
	comp=[i["name"] for i in comp]
	if not items:
		items=frappe.db.get_all("Sales Invoice",filters=[["company",'in',comp],["docstatus","in",[1]],["zatca_status","in",["Pending","Rejected"]]],fields=["name","company"])
		items=[i["name"] for i in items]
	else:
		items=items.replace("[","").replace("]","").replace(" ","").replace("\"","").replace("'","")
		items=items.split(",")
	cleared=0
	reported=0
	reportedno=0
	clearedno=0
	dis=False
	for i in items:
		item=frappe.get_doc("Sales Invoice",i)
		if item.docstatus !=1 or  item.zatca_status not in ["Pending","Rejected"]:
			break
		if not item.xml_path:
			item.first_xml(True)
		if item.simple:
			rep=item.report(True)
			if rep:
				reported+=1
			else:
				reportedno+=1
		else:
			cle=item.clearance(True)
			if cle:
				cleared+=1
			else:
				clearedno+=1
	msg=""
	if reported+reportedno==0 and cleared+clearedno==0:
		frappe.msgprint(_("No pending invoices / Zatca is disabled or running compliance checks."),indicator="orange")
	else:
		if reportedno+clearedno==0:
			msg+="<span style='color:green;'>"+_("All invoices has been cleared/reported.")+"</span><br>"
		if reported+cleared==0:
			msg+="<span style='color:red;'>"+_("Failed to report/clear invoices")+"</span><br>"
		if reported+cleared!=0 and reportedno+clearedno!=0:
			msg+="<span style='color:orange;'>"+_("Invoices are partially cleared/reported")+"</span><br>"
		if cleared+clearedno>0:
			msg+=_("B2B invoices: cleared {}, rejected {}, total {}.").format(cleared,clearedno,cleared+clearedno)+"</br>"
		if reported+reportedno>0:
			msg+=_("B2C invoices: reported {}, rejected {}, total {}.").format(reported,reportedno,reported+reportedno)+"</br>"
		frappe.msgprint(msg)
@frappe.whitelist()
def clears_report(invoice):
	invoice=frappe.get_doc("Sales Invoice",invoice)
	if invoice.simple:
		if not invoice.xml_path:
			invoice.first_xml()
		invoice.report()
	else:
		if not invoice.xml_path:
			invoice.first_xml()
		invoice.clearance()
def get_urli(endpoint):
	if endpoint=="Developer Portal" or endpoint=="Developer":
		return("https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal")
	elif endpoint=="Simulation":
		return("https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation")
	else:
		return("https://gw-fatoora.zatca.gov.sa/e-invoicing/core")
def comment(invoice,msg):
	com=frappe.new_doc("Comment")
	com.comment_type="Comment"
	com.reference_doctype="Sales Invoice"
	com.reference_name=invoice
	com.content=msg
	com.insert()
def truncate(f):
    return math.floor(f * 100) / 100
def num(a):
	#return str(truncate(abs(a)))
	return("%.2f" % abs(a))
def alert(msg,color="green"): 
	frappe.msgprint( _(msg), alert=True, indicator=color)
def msgprint(message,title="Notification",indicator="green"):
	frappe.msgprint({
	    title: _(title),
	    indicator: indicator,
	    message: _(message)
});
