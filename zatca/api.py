import frappe
from frappe import _
import base64
import requests
from zatca.e_invoicing import compliance_checks


@frappe.whitelist()
def renew(company,new_otp=None):
	if "Zatca Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("You don't have permissions to manage zatca settings, Contact administration."))
	company=frappe.get_doc("Company",company)
	otp,csr,version=validate(company)
	if new_otp!=company.otp:
		company.otp=new_otp
		otp=new_otp
	urli=get_urli(company.custom_api_endpoint)
	url = urli+"/production/csids"
	username=company.pcsid_username or ""
	password=company.get_password("pcsid_password") or ""
	if not username or not password :
		alert("Username/password is missing","red")
	auth = username+':'+password
	binary_auth = auth.encode('utf-8')
	autorization_binary = base64.b64encode(binary_auth)
	autorization = autorization_binary.decode('utf-8')
	Headers = { 'accept' : 'application/json', 'Accept-Version' : version,'OTP':otp, 'Content-Type': 'application/json' ,'Authorization': 'Basic '+autorization}
	data={'csr':csr}
	response = requests.patch(url, json=data, headers=Headers)
	if response.status_code==401:
		frappe.msgprint(_("Unothorized"))
		return
	print (response.text)
	if response.status_code == 200:
		js=response.json()
		username=js["binarySecurityToken"]
		password=js["secret"]
		company.pcsid_requestid=js["requestID"]
		company.pcsid_username=username
		company.pcsid_password=password
		company.custom_enabled_since=frappe.utils.get_datetime()
		company.save()
		frappe.db.commit()
		alert("Production CSID renewed successfully")
		return True
	else:
		frappe.msgprint(_("Something wen wrong")+"<br>"+_("Invalid Request"),("Error"),"red")

@frappe.whitelist()
def compliance(company,new_otp=None):
	if "Zatca Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("You don't have permissions to manage zatca settings, Contact administration."))
	company=frappe.get_doc("Company",company)
	if new_otp!=company.otp:
		company.otp=new_otp
		otp=new_otp
	otp,csr,version=validate(company)
	if not otp:
		frappe.throw(_("Missing OTP"))
	if not csr:
		frappe.throw(_("Missing CSR"))
	if new_otp!=otp:
		company.otp=new_otp
		otp=new_otp
	urli=get_urli(company.custom_api_endpoint)
	url = urli+"/compliance"
	Headers = { 'accept' : 'application/json', 'OTP': otp, 'Accept-Version' :version , 'Content-Type': 'application/json' }
	data={'csr':csr}
	try:
		response = requests.post(url, json=data, headers=Headers)
	except:
		frappe.throw(_("Failed to fetch data from Zatca server."))
	code=response.status_code
	if (str(code)=="200"):
		js=response.json()
		id=js["requestID"]
		username=js["binarySecurityToken"]
		password=js["secret"]
		company.ccsid_requestid=id
		company.ccsid_username=username
		company.ccsid_password=password
		company.custom_zatca_status="Compliance Check"
		company.custom_standard_check=0
		company.custom_standard_credit_check=0
		company.custom_standard_debit_check=0
		company.custom_simple_check=0
		company.custom_simple_credit_check=0
		company.custom_simple_debit_check=0
		msg=_("Based on the invoice type that has been added to the CSR, validation checks will be automatically generating before onboarding")+"<br>"
		checks=[]
		if company.t=="1":
			checks.append(_("Standard Tax Invoice (B2B)"))
			checks.append(_("Standard Debit Note (B2B)"))
			checks.append(_("Standard Credit Note (B2B)"))
		if company.s=="1":
			checks.append(_("Simplified Tax Invoice (B2C)"))
			checks.append(_("Simplified Debit Note (B2C)"))
			checks.append(_("Simplified Credit Note (B2C)"))
		for c in checks:
			msg+="- "+c+"<br>"
		msg+=_("Click Onboarding to continue")
		frappe.msgprint(msg,"<span style='color:green;'>"+_("Compliance CSID generated successfully")+"</span>")
		company.save()
		frappe.db.commit()
		return(1)
	else:
		try:
			if code==404:
				frappe.throw(_("Failed to fetch data from Zatca server."))
			else:
				frappe.throw(response.text)
		except:
			frappe.msgprint(_(response.text),"red")
			return(-1)
		
@frappe.whitelist()
def onboarding(company,new_otp=None):
	if "Zatca Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("You don't have permissions to manage zatca settings, Contact administration."))
	company=frappe.get_doc("Company",company)
	private_key=company.private_key
	if not private_key :
		frappe.throw(_("Missing Private Key"))
	if new_otp!=company.otp:
		company.otp=new_otp
		otp=new_otp
	otp,csr,version=validate(company)
	if not otp:
		frappe.throw(_("Missing OTP"))
	if not csr:
		frappe.throw(_("Missing CSR"))
	urli=get_urli(company.custom_api_endpoint)
	url = urli+"/compliance"
	Headers = { 'accept' : 'application/json', 'OTP': otp, 'Accept-Version' :version , 'Content-Type': 'application/json' }
	data={'csr':csr}
	print(data)
	print(url)
	print(Headers)
	try:
		print("sending ccsid request")
		response = requests.post(url, json=data, headers=Headers)
	except:
		frappe.throw(_("Failed to fetch data from Zatca server."))
	print("request sent")
	code=response.status_code
	if (str(code)=="200"):
		js=response.json()
		id=js["requestID"]
		username=js["binarySecurityToken"]
		password=js["secret"]
		company.ccsid_requestid=id
		company.ccsid_username=username
		company.ccsid_password=password
	else:
		try:
			if code==404:
				frappe.throw(_("Failed to fetch data from Zatca server."))
			else:
				frappe.throw(response.text)
		except:
			frappe.msgprint(_(response.text),"red")
			return(-1)	
	print("compliance done")
	missing=[]
	if company.t and company.t!="0":
		missing=["Standard Invoice","Standard Credit Invoice","Standard Debit Invoice"]
	if company.s and company.s !="0":
		missing+=["Simple Invoice","Simple Credit Invoice","Simple Debit Invoice"]
	private_key=base64.b64encode(private_key.encode("utf-8")).decode("utf-8")
	a=compliance_checks(id,username,password,private_key,company.custom_api_endpoint,missing,company.tax_id)
	if a!= len(missing):
		frappe.throw(_("Compliance check error"))
	#else:
		#frappe.msgprint("<span>"+str(a)+_(" Compliance Checks completed.")+"</span><br>")
	urli=get_urli(company.custom_api_endpoint)
	url = urli+"/production/csids"
	version=company.accept_version
	auth = username+':'+password
	binary_auth = auth.encode('utf-8')
	autorization_binary = base64.b64encode(binary_auth)
	autorization = autorization_binary.decode('utf-8')
	Headers = { 'accept' : 'application/json', 'Accept-Version' : version, 'Content-Type': 'application/json' ,'Authorization': 'Basic '+autorization}
	data={'compliance_request_id':id}
	try:
		response = requests.post(url, json=data, headers=Headers)
	except:
		frappe.throw(_("Failed to fetch data from Zatca server."))
	code=response.status_code
	if (str(code)=="200"):
		js=response.json()
		company.pcsid_requestid=js["requestID"]
		company.pcsid_username=js["binarySecurityToken"]
		company.pcsid_password=js["secret"]
		company.custom_zatca_status="Enabled"
		company.custom_enabled_since=frappe.utils.get_datetime()
		alert("Production CSID generated successfully")
		frappe.msgprint("<span>"+_("Onboarding Completed, verify the connection in Fatoora Portal.")+"</span><br>")
	else:
		try:
			alert(js["message"],"red")
		except:
			alert(response.text,"red")
			return(-1)
		return(-1)
	company.save()
	frappe.db.commit()
	return(1)



@frappe.whitelist()
def clear(company):
	if "Zatca Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("You don't have permissions to manage zatca settings, Contact administration."))
	try:
		company=frappe.get_doc("Company",company)
		company.ccsid_requestid=""
		company.ccsid_username=""
		company.ccsid_password=""
		company.pcsid_requestid=""
		company.pcsid_username=""
		company.pcsid_password=""
		company.csr=""
		company.otp=""
		company.custom_zatca_status="Disabled"
		company.custom_enabled_since=None
		company.save()
		frappe.db.commit()
		alert("API data cleared")
		return(1)
	except:
		alert("Unknown error","red")


def validate(company):
	if not company.otp:
		frappe.throw(_("OTP is missing"))
	if not company.csr:
		frappe.throw(_("CSR is missing"))
	return company.otp, company.csr , company.accept_version

def get_urli(endpoint):
	if endpoint=="Developer Portal":
		return("https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal")
	elif endpoint=="Simulation":
		return("https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation")
	else:
		return("https://gw-fatoora.zatca.gov.sa/e-invoicing/core")
			

def error(msg): 
	frappe.throw(title=_("Error"),msg=_(msg)) 
def alert(msg,color="green"): 
	frappe.msgprint( _(msg),
 		alert=True,
		indicator=color
	)
