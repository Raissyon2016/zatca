import frappe
import base64,os,random,string
import lxml.etree as ETT
import xml.etree.ElementTree as ET
from hashlib import sha256
from OpenSSL import crypto
from ecdsa import SigningKey, VerifyingKey
from datetime import datetime
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from zatca.qr import qr_code
import requests
import json
from uuid import UUID

class Struct:
	def __init__(self,**entries):
		self.__dict__.update(entries)
	def __getattr__(self,item):
		return None
		
		
def log(name,type_,status,xml,reason=None):
	if not reason:
		reason=""
	log=frappe.get_doc({
	"doctype":"Zatca Log",
	"zatca_client":name,
	"type":type_,
	"status":status,
	"xml":xml,
	"reason":reason
	})
	log.insert(ignore_permissions=True)
	frappe.db.commit()
		
def validate_token(token):
	if not token or ":" not in token:
		return [{"code":"Unothorized","message":"You are not permitted to access this resource"}]
	key,secret=token.split(":")
	auth=frappe.db.get_all("Zatca Auth",filters={"key":key,"secret":secret},fields=["expiration","disabled","name"])
	if len(auth)==0:
		return None , [{"code":"Unothorized","message":"You are not permitted to access this resource"}]
	if auth[0]["disabled"]:
		return None, [{"code":"Unothorized","message":"Token Disabled"}]
	ex=auth[0]["expiration"]
	today=frappe.utils.get_datetime()
	difference=(ex-today).days
	if difference<0:
		return None, [{"code":"Unothorized","message":"Token expired"}]
	return auth[0]["name"], []
@frappe.whitelist(allow_guest=True)
def test():
	token=frappe.get_request_header("Token")
	n,v=validate_token(token)
	if  v:
		frappe.response["http_status_code"]=401
		frappe.response["errors"]=v
		return
	frappe.response["http_status_code"]=200
	customer=frappe.db.get_value("Zatca Auth",n,"customer")
	frappe.response["customer"]=customer
	
def validate_renew(d):
	errors=[]
	if not d.csr:
		errors.append({"code":"Missing CSR","message":"CSR is a required field"})
	if not d.otp:
		errors.append({"code":"Missing OTP","message":"OTP is a required field"})
	else:
		try:
			a=int(d.otp)
			if len(str(a))!=6:
				errors.append({"code":"Invalid CSR","message":"CSR must be a 6 digits integer/string"})
		except:
			errors.append({"code":"Invalid CSR","message":"CSR must be a 6 digits integer/string"})
	if not d.pcsid_token:
		errors.append({"code":"Missing certificate","message":"pcsid_token is a required field"})
	if not d.pcsid_secret:
		errors.append({"code":"Missing certificate secret","message":"pcsid_secret is a required field"})
	if not d.endpoint:
		errors.append({"code":"Missing Endpoint","message":"Api endpoint is a required field"})
	else:
		e=d.endpoint
		if e not in ["Developer Portal","Simulation","Production","Developer"]:
			errors.append({"code":"Invalid Endpoint","message":"Api endpoint must be one of the folowing: Developer Portal, Simulation, Production"})
	return errors
@frappe.whitelist(allow_guest=True)
def renew():
	token=frappe.get_request_header("Token")
	n,v=validate_token(token)
	if  v:
		frappe.response["http_status_code"]=401
		frappe.response["errors"]=v
		return
	errors=validate_renew(frappe.form_dict)
	if len(errors)>0:
		frappe.response["http_status_code"]=400
		frappe.response["errors"]=errors
		return
	urli=get_urli(frappe.form.endpoint)
	url = urli+"/production/csids"
	csr=frappe.form_dict.csr
	otp=frappe.form_dict.otp
	auth =frappe.form_dict.pcsid_token+":"+frappe.form_dict.pcsid_secret
	binary_auth = auth.encode('utf-8')
	autorization_binary = base64.b64encode(binary_auth)
	autorization = autorization_binary.decode('utf-8')
	Headers = { 'accept' : 'application/json', 'Accept-Version' : "V2",'OTP':otp, 'Content-Type': 'application/json' ,'Authorization': 'Basic '+autorization}
	data={'csr':csr}
	response = requests.patch(url, json=data, headers=Headers)
	if response.status_code == 200:
		js=response.json()
		username=js["binarySecurityToken"]
		password=js["secret"]
		id_=js["requestID"]
		frappe.response["http_status_code"]=200
		frappe.response["pcsid_requestid"]=id_
		frappe.response["pcsid_token"]=username
		frappe.response["pcsid_secret"]=password
	else:
		frappe.response["http_status_code"]=400
		frappe.response["error"]=response_.text


@frappe.whitelist(allow_guest=True)
def clear():
	token=frappe.get_request_header("Token")
	n,v=validate_token(token)
	
	if  v:
		frappe.response["http_status_code"]=401
		frappe.response["errors"]=v
		return
	
	errors=validate_report(frappe.form_dict)
	
	if len(errors)>0:
		frappe.response["http_status_code"]=400
		frappe.response["errors"]=errors
		return
	urli=get_urli(frappe.form.endpoint)
	url=urli+"/invoices/clearance/single"
	Headers = { 'accept' : 'application/json', 'Accept-Version' : "V2", 'Content-Type': 'application/json', 'Accept-Language': 'en' }
	Headers = { 'accept' : 'application/json', 'Clearance-Status': '1', 'Accept-Version' : "V2", 'Content-Type': 'application/json', 'Accept-Language': 'en' }
	auth =frappe.form_dict.pcsid_token+":"+frappe.form_dict.pcsid_secret
	binary_auth = auth.encode('utf-8')
	autorization_binary = base64.b64encode(binary_auth)
	autorization = autorization_binary.decode('utf-8')
	Headers["Authorization"]="Basic "+autorization
	data={"invoiceHash":frappe.form_dict.hash,"uuid":frappe.form_dict.uuid,"invoice":frappe.form_dict.invoice}
	response = requests.post(url, data=json.dumps(data), headers=Headers)
	
	try:
		rj=response.json()
		if response.status_code in [200,201,202,400]:
			status=rj["clearanceStatus"]
			type_="Clear Invoice"
			reason=None
			if status=="NOT_CLEARED":
				reason=""
				for i in rj["validationResults"]["errorMessages"]:
					reason+=i["message"]+"\n"
			log(n,type_,status,frappe.form_dict.invoice,reason)
			
		frappe.response["http_status_code"]=200
		frappe.response["result"]=response.json()
	except:
		frappe.response["http_status_code"]=400
		frappe.response["result"]=[]
		frappe.response["errors"]=[{"code":"Report error","message":"unknown error while reporting invoice"}]
		

@frappe.whitelist(allow_guest=True)
def report():
	token=frappe.get_request_header("Token")
	n,v=validate_token(token)
	if  v:
		frappe.response["http_status_code"]=401
		frappe.response["errors"]=v
		return
	errors=validate_report(frappe.form_dict)
	
	if len(errors)>0:
		frappe.response["http_status_code"]=400
		frappe.response["errors"]=errors
		return
	urli=get_urli(frappe.form.endpoint)
	url=urli+"/invoices/reporting/single"
	Headers = { 'accept' : 'application/json', 'Accept-Version' : "V2", 'Content-Type': 'application/json', 'Accept-Language': 'en' }
	Headers = { 'accept' : 'application/json', 'Clearance-Status': '1', 'Accept-Version' : "V2", 'Content-Type': 'application/json', 'Accept-Language': 'en' }
	auth =frappe.form_dict.pcsid_token+":"+frappe.form_dict.pcsid_secret
	
	binary_auth = auth.encode('utf-8')
	autorization_binary = base64.b64encode(binary_auth)
	autorization = autorization_binary.decode('utf-8')
	Headers["Authorization"]="Basic "+autorization
	data={"invoiceHash":frappe.form_dict.hash,"uuid":frappe.form_dict.uuid,"invoice":frappe.form_dict.invoice}
	response = requests.post(url, data=json.dumps(data), headers=Headers)
	try:
		rj=response.json()
		
		if response.status_code in [200,201,202,400]:
			status=rj["reportingStatus"]
			reason=None
			if status=="NOT_REPORTED":
				reason=""
				for i in rj["validationResults"]["errorMessages"]:
					reason+=i["message"]+"\n"
			type_="Report Invoice"
			log(n,type_,status,frappe.form_dict.invoice,reason)
		frappe.response["http_status_code"]=200
		frappe.response["result"]=response.json()
	except:
		frappe.response["http_status_code"]=400
		frappe.response["result"]=[]
		frappe.response["errors"]=[{"code":"Report error","message":"unknown error while reporting invoice"}]
	
	
@frappe.whitelist(allow_guest=True)
def check():
	token=frappe.get_request_header("Token")
	n,v=validate_token(token)
	if  v:
		frappe.response["http_status_code"]=401
		frappe.response["errors"]=v
		return
	errors=validate_check(frappe.form_dict)
	if len(errors)>0:
		frappe.response["http_status_code"]=400
		frappe.response["errors"]=errors
		return
	urli=get_urli(frappe.form.endpoint)
	url=urli+"/compliance/invoices"
	Headers = { 'accept' : 'application/json', 'Accept-Version' : "V2", 'Content-Type': 'application/json', 'Accept-Language': 'en' }
	auth =frappe.form_dict.ccsid_token+":"+frappe.form_dict.ccsid_secret
	binary_auth = auth.encode('utf-8')
	autorization_binary = base64.b64encode(binary_auth)
	autorization = autorization_binary.decode('utf-8')
	Headers["Authorization"]="Basic "+autorization
	data={"invoiceHash":frappe.form_dict.hash,"uuid":frappe.form_dict.uuid,"invoice":frappe.form_dict.invoice}
	try:
		response = requests.post(url, data=json.dumps(data), headers=Headers)
	except:
		frappe.response["http_status_code"]=400
		frappe.response["result"]=[]
		frappe.response["errors"]=[{"code":"Zatca Error","message":"Failed to fetch data from zatca."}]
		return
	try:
		frappe.response["http_status_code"]=200
		frappe.response["result"]=response.json()
	except:
		frappe.response["http_status_code"]=400
		frappe.response["result"]=[]
		frappe.response["errors"]=[{"code":"Compliance check error","message":"unknown error in compliance check"}]
	
def validate_check(d):
	return []
def validate_report(d):
	return []

def compliance_check(ccsid_username,ccsid_password,hash_,uuid,invoice,endpoint):
	#frappe.throw(invoice)
	urli=get_urli(endpoint)
	url=urli+"/compliance/invoices"
	Headers = { 'accept' : 'application/json', 'Accept-Version' : "V2", 'Content-Type': 'application/json', 'Accept-Language': 'en' }
	auth =ccsid_username+":"+ccsid_password
	binary_auth = auth.encode('utf-8')
	autorization_binary = base64.b64encode(binary_auth)
	autorization = autorization_binary.decode('utf-8')
	Headers["Authorization"]="Basic "+autorization
	data={"invoiceHash":hash_,"uuid":uuid,"invoice":invoice}
	response = requests.post(url, data=json.dumps(data), headers=Headers)
	
	try:
		r=response.json()["reportingStatus"]
		c=response.json()["clearanceStatus"]
		a=r if r else c
		print(response.text)
		print(a)
		if r=="REPORTED" or c=="CLEARED":
			return 1
		else:
			return 0
	except:
		return 0
	
	
def validate_onboarding(d):
	errors=[]
	if not d.csr:
		errors.append({"code":"Missing CSR","message":"CSR is a required field"})
	if not d.otp:
		errors.append({"code":"Missing OTP","message":"OTP is a required field"})
	else:
		try:
			a=d.otp
			if len(str(a))!=6:
				errors.append({"code":"Invalid OTP","message":"OTP must be a 6 digits integer/string"})
			a=int(a)
		except:
			errors.append({"code":"Invalid OTP","message":"OTP must be a 6 digits integer/string"})
	if not d.tax_id:
		errors.append({"code":"Missing Tax Id","message":"Company Tax ID is a required field"})
	else:
		tax_id=str(d.tax_id)
		if len(tax_id)!=15 or not tax_id.isnumeric() or tax_id[0]!="3" or tax_id[-1]!="3"  :
			errors.append({"code":"Invalid Tax id","message":"company tax id must be 15 digits, begins with 3 and ends with 3."})
	if not d.private_key:
		errors.append({"code":"Missing Private Key","message":"Private key is a required field"})
	if not d.endpoint:
		errors.append({"code":"Missing Endpoint","message":"Api endpoint is a required field"})
	else:
		e=d.endpoint
		if e not in ["Developer Portal","Simulation","Production","Developer"]:
			errors.append({"code":"Invalid Endpoint","message":"Api endpoint must be one of the folowing: Developer Portal, Simulation, Production"})
	if d.invoice_type:
		if d.invoice_type not in ["11","01","10"]:
			errors.append({"code":"Invalid Invoice Type","message":"Invoice Type must be a 2 char string representing standard and simple invoices by 0 or 1."})
	return errors
		
		
@frappe.whitelist(allow_guest=True)
def onboarding():
	token=frappe.get_request_header("Token")
	n,v=validate_token(token)
	if  v:
		frappe.response["http_status_code"]=401
		frappe.response["errors"]=v
		return
	#csr=base64.b64decode(frappe.form_dict.csr).decode("utf-8")
	errors=validate_onboarding(frappe.form_dict)
	if len(errors)>0:
		frappe.response["http_status_code"]=400
		frappe.response["errors"]=errors
		return
	tax_id=frappe.form_dict.tax_id
	csr_=frappe.form_dict.csr
	otp=frappe.form_dict.otp
	urli=get_urli(frappe.form.endpoint)
	url = urli+"/compliance"
	Headers = { 'accept' : 'application/json', 'OTP': otp, 'Accept-Version' :"V2" , 'Content-Type': 'application/json' }
	data={'csr':csr_}
	response_ = requests.post(url, json=data, headers=Headers)
	code=response_.status_code
	missing=[]
	if frappe.form_dict.invoice_type:
		t=frappe.form_dict.invoice_type
		if t[0]=="1":
			missing=["Standard Invoice","Standard Credit Invoice","Standard Debit Invoice"]
		if t[1]=="1":
			missing=missing+["Simple Credit Invoice","Simple Debit Invoice","Simple Invoice"]
		le=len(missing)
	else:
		missing=None	
		le=6
	if (str(code)=="200"):
		js=response_.json()
		ccsid_requestid=js["requestID"]
		ccsid_token=js["binarySecurityToken"]
		ccsid_secret=js["secret"]
		a=compliance_checks(ccsid_requestid,ccsid_token,ccsid_secret,frappe.form_dict.private_key,frappe.form_dict.endpoint,missing,tax_id)
		
		if a==le:
			print("checks good")
			url = urli+"/production/csids"
			auth = ccsid_token+':'+ccsid_secret
			binary_auth = auth.encode('utf-8')
			autorization_binary = base64.b64encode(binary_auth)
			autorization = autorization_binary.decode('utf-8')
			Headers = { 'accept' : 'application/json', 'Accept-Version' : "V2", 'Content-Type': 'application/json' ,'Authorization': 'Basic '+autorization}
			data={'compliance_request_id':ccsid_requestid}
			response = requests.post(url, json=data, headers=Headers)
			code=response.status_code
			if (str(code)=="200"):
				js=response.json()
				pcsid_requestid=js["requestID"]
				pcsid_token=js["binarySecurityToken"]
				pcsid_secret=js["secret"]
				frappe.response["ccsid_requestid"]=ccsid_requestid
				frappe.response["ccsid_token"]=ccsid_token
				frappe.response["ccsid_secret"]=ccsid_secret
				frappe.response["pcsid_requestid"]=pcsid_requestid
				frappe.response["pcsid_token"]=pcsid_token
				frappe.response["pcsid_secret"]=pcsid_secret
			else:
				frappe.response["http_status_code"]=400
				frappe.response["error"]=response_.text
			
		else:
			frappe.response["http_status_code"]=400
			frappe.response["error"]="Compliance Checks Failed"
	else:
		
		frappe.response["http_status_code"]=400
		frappe.response["error"]=response_.text
	
@frappe.whitelist(allow_guest=True)
def csr():
	token=frappe.get_request_header("Token")
	n,v=validate_token(token)
	if  v:
		frappe.response["http_status_code"]=401
		frappe.response["errors"]=v
		return
	errors=validate_csr(frappe.form_dict)
	if len(errors)>0:
		frappe.response["http_status_code"]=400
		frappe.response["errors"]=errors
		return
	d=frappe.form_dict
	template_path="assets/zatca/zatca/template.cnf"
	cname="".join(random.choices("abcdefghijklmnopqrstuwxyz",k=8))
	try:
		f = open(template_path, "r")
		text=f.read()
		text=config(text,d)
		name="assets/zatca/zatca/"+cname+"config.cnf"
		f=open(name,"w")
		f.write(text)
		f.close()
	except:
		return(-1)
	#create private key
	os.system("openssl ecparam -name secp256k1 -genkey -noout -out assets/zatca/zatca/"+cname+"privatekey.pem")
	pk=open("assets/zatca/zatca/"+cname+"privatekey.pem","r")
	private_key=pk.read()
	pk.close()
	#os.remove("assets/zatca/zatca/"+cname+"privatekey.pem")
	#create public key
	os.system("openssl ec -in assets/zatca/zatca/"+cname+"privatekey.pem -pubout -conv_form compressed -out assets/zatca/zatca/"+cname+"publickey.pem")
	#create bin file
	a=os.popen("openssl base64 -d -in assets/zatca/zatca/"+cname+"publickey.pem -out assets/zatca/zatca/"+cname+"publickey.bin").read()
	#generate csr
	a=os.popen("openssl req -new -sha256 -key assets/zatca/zatca/"+cname+"privatekey.pem -extensions v3_req -config assets/zatca/zatca/"+cname+"config.cnf -out assets/zatca/zatca/"+cname+"csr.csr").read()
	f=open("assets/zatca/zatca/"+cname+"csr.csr","r")
	csr=f.read()
	#csr=csr.replace("\n","")
	csr=base64.b64encode(csr.encode("utf-8")).decode("utf-8")
	private_key=base64.b64encode(private_key.encode("utf-8")).decode("utf-8")
	os.remove("assets/zatca/zatca/"+cname+"csr.csr")
	os.remove("assets/zatca/zatca/"+cname+"privatekey.pem")
	os.remove("assets/zatca/zatca/"+cname+"publickey.pem")
	os.remove("assets/zatca/zatca/"+cname+"publickey.bin")
	os.remove(name)
	frappe.response["csr"]=csr
	frappe.response["private_key"]=private_key

def config(text,v):
	certificate_template="ASN1:PRINTABLESTRING:ZATCA-Code-Signing"
	if v.simulation:
		certificate_template="ASN1:PRINTABLESTRING:PREZATCA-Code-Signing"
	settings=frappe.get_doc("Zatca Settings")
	if settings.sn:
		sn=settings.sn
	else:
		sn="1-Baha|2-version15|3-24c359bd59af"
	country = v.country or "SA"
	a=text.replace("{title}",v.invoice_type)
	a=a.replace("{c}",country)
	a=a.replace("{ou}",v.ou)
	a=a.replace("{o}",v.company_name)
	a=a.replace("{cn}",v.common_name)
	a=a.replace("{sn}",sn)
	a=a.replace("{uid}",v.uid)
	a=a.replace("{address}",v.registredAddress)
	a=a.replace("{category}",v.businessCategory)
	a=a.replace("{email}",v.email)
	a=a.replace("{certificate_template}",certificate_template)
	return(a)

def validate_csr(d):
	errors=[]
	if not d.company_name:
		errors.append({"code":"Missing Company Name","message":"company is a required field"})
	if not d.ou:
		errors.append({"code":"Missing Organization Unit Name","message":"Organization unit name is a required field"})
	if not d.uid:
		errors.append({"code":"Missing UID","message":"company uid (tax id) is a required field"})
	else:
		tax_id=str(d.uid)
		if len(tax_id)!=15 or not tax_id.isnumeric() or tax_id[0]!="3" or tax_id[-1]!="3"  :
			errors.append({"code":"Invalid UID","message":"company uid (tax id) must be 15 digits, begins with 3 and ends with 3."})
		if tax_id[10]=="1":
			ou=str(d.ou) if d.ou else ""
			if len(ou)!=10 or not ou.isnumeric():
				errors.append({"code":"Invalid Organization Unit Name","message":"In case of VAT Groups, organization unit name must be a 10-digits TIN."})
	if not d.registredAddress:
		errors.append({"code":"Missing Company address","message":"company registred address is a required field"})
	if not d.email:
		errors.append({"code":"Missing Email","message":"company email is a required field"})
	else:
		if not validate_email(d.email):
			errors.append({"code":"Invalid Email","message":"Invalid email address"})
	if not d.businessCategory:
		errors.append({"code":"Missing Busienss Category","message":"business category is a required field"})
	if not d.common_name:
		errors.append({"code":"Missing Common Name","message":"common name is a required field"})
	if not d.invoice_type:
		errors.append({"code":"Missing Invoice Type","message":"invoice type is a required field"})
	else:
		try:
			if len(str(d.invoice_type))!=4:
				errors.append({"code":"Invalid Invoice Type","message":"invoice type must be 4-digit numerical input using 0 & 1 mapped to “TSCZ”"})
			else:			
				for i in str(d.invoice_type):
					if i not in ["0","1"]:
						errors.append({"code":"Invalid Invoice Type","message":"invoice type must be 4-digit numerical input using 0 & 1 mapped to “TSCZ”"})
						break
		except:
			errors.append({"code":"Invalid Invoice Type","message":"invoice type must be 4-digit numerical input using 0 & 1 mapped to “TSCZ”"})
	if d.simulation:
		if d.simulation not in [1,0,True,False]:
			errors.append({"code":"Invalid field","message":"Simulation field must be of Boolean type"})
	if d.sn:
		sn=str(d.sn)
		if sn[:2]!="1-":
			errors.append({"code":"Invalid Serial Number","message":"Serial number must be in the format \"1-… |2-… |3-…\""})
		try:
			if "1-" not in sn or  "|2-" not in sn or  "|3-" not in sn:
				errors.append({"code":"Invalid Serial Number","message":"Serial number must be in the format \"1-… |2-… |3-…\""})
		except:
			errors.append({"code":"Invalid Serial Number","message":"Serial number must be in the format \"1-… |2-… |3-…\""})
	return errors
		
		
def compliance_checks(id_,username,password,private_key,endpoint,missing=None,tax_id="326548754865463"):
	if not missing:
		missing=["Standard Invoice","Standard Credit Invoice","Standard Debit Invoice","Simple Credit Invoice","Simple Debit Invoice","Simple Invoice"]
	data={
		"id":"123456",	
		"invoice_type":"standard",
		"uuid":"5218f5ae-771b-44f8-8060-c8e8313c6dbc",
		"cr_number":"123456",
		"pih":"NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ==",
   
  		 "issue_date":"2023-01-01",
 		  "issue_time":"01:30:00",
  		  "delivery_date":"2023-01-01",
  		  
  		  "grand_total":"1.15",
 		   "taxable_amount":1,
 		   "net_total":1,
 		   "tax_rate":15,
 		   "tax_amount":0.15,
 		   "is_debit_note":0,
 		   "is_credit_note":0,
 		   "supplier":{"name":"baha","tax_id":tax_id,"street_name":"street_name","building_number":1234,"plot":"123","postal_code":"12345","subdivision":"Riyadh","city":"Riyadh"},
  		  "customer":{"name":"customer","tax_id":326547,"street_name":"street_name","building_number":1234,"plot":"123","postal_code":"12345","subdivision":"Riyadh","city":"Riyadh"},
  		  "itemlines":[{"item_name":"1","qty":1,"rate":1,"tax_amount":0.15,"tax_rate":15,"net_amount":1,"grand_total":1.15}]
	}
	total=0
	for m in missing:
		data["is_debit_note"]=0
		data["is_credit_note"]=0
		data["invoice_type"]="standard"
		if "Simple" in m:
			data["invoice_type"]="simple"
			data["certificate"]=username
			data["private_key"]=private_key
		if "Credit" in m:
			data["is_credit_note"]=1
			data["reference"]="123"
		if "Debit" in m :
			data["is_debit_note"]=1
			data["reference"]="123"
		data_=Struct(**data)
		r=xml_(data_)
		
		if 1:
			hash_=r["hash"]
			
			invoice=r["invoice"]
			
			to=compliance_check(username,password,hash_,"5218f5ae-771b-44f8-8060-c8e8313c6dbc",invoice,endpoint)
			
			if to==0:
				r=xml_(data_)
				hash_=r["hash"]
				invoice=r["invoice"]
				to=compliance_check(username,password,hash_,"5218f5ae-771b-44f8-8060-c8e8313c6dbc",invoice,endpoint)
			total+=to
		else:
			
			continue
	return total
@frappe.whitelist(allow_guest=True)
def xml():
	token=frappe.get_request_header("Token")
	n,v=validate_token(token)
	if  v:
		frappe.response["http_status_code"]=401
		frappe.response["errors"]=v
		return
	errors=validate(frappe.form_dict)
	if len(errors)>0:
		frappe.response["http_status_code"]=400
		frappe.response["errors"]=errors
		return
	r=xml_(frappe.form_dict)
	if "hash" in r.keys():
		frappe.response["hash"]=r["hash"]
	if "file_name" in r.keys():
		frappe.response["file_name"]=r["file_name"]
	if "invoice" in r.keys():
		frappe.response["invoice"]=r["invoice"]
	if "qr_code" in r.keys():
		frappe.response["qr_code"]=r["qr_code"]
	if "http_status_code" in r.keys():
		frappe.response["http_status_code"]=r["http_status_code"]
		frappe.response["warnings"]=r["warnings"]
		frappe.response["errors"]=r["errors"]

def xml_(d):
	warnings=[]
	typee=d.invoice_type
	taxes=d.tax_amount
	if typee.lower()=="simple":
		type_code_name="0200000"
		f=open("assets/zatca/templates/simple_invoice.xml","r")
	else:
		type_code_name="0100000"
		f=open("assets/zatca/templates/standard_invoice.xml","r")
	xml=f.read()
	if typee.lower()=="standard":
		xml=xml.replace("{ext:UBLExtensions}","")
		xml=xml.replace("{QR}","")
		
	taxes=num(taxes)
	tax_rate=d.tax_rate
	qr_code=""
	tax_category="S"
	tax_category=d.tax_category
	if not tax_category and tax_rate >0:
		tax_category="S"
	tax_code=""
	tax_reason=""
	if float(taxes)==0:
		tax_category="Z"
		tax_code=d.tax_code
		tax_reason=d.tax_reason
		if not tax_code:
			warnings.append({"code":"Missing Tax Code","message":"for Tax invoice with total_taxes_and_charges equal to 0, tax_code is a required field."})
		if not tax_reason:
			warnings.append({"code":"Missing Tax Reason","message":"for Tax invoice with total_taxes_and_charges equal to 0, tax_reason is a required field."})
		if tax_code in ["VATEX-SA-29","VATEX-SA-29-7","VATEX-SA-30"]:
			tax_category="E"
		tax_code="<cbc:TaxExemptionReasonCode>"+tax_code+"</cbc:TaxExemptionReasonCode>" if tax_code else ""
		tax_reason="<cbc:TaxExemptionReason>"+tax_reason+"</cbc:TaxExemptionReason>" if tax_reason else ""
	
	
	type_code="388"
	debit_credit_reason=""
	billing_reference=""
	
	credit_note=d.is_credit_note
	debit_note=d.is_debit_note
	if credit_note:
		type_code="381"
		credit_against=d.reference
		credit_reason=d.credit_reason
		if not credit_reason:
			warnings.append({"code":"Missing Credit Note Reason","message":"for a Credit note invoice, credit reason is a required field."})
			debit_credit_reason="<cbc:InstructionNote>CANCELLATION_OR_TERMINATION</cbc:InstructionNote>"
		else:
			debit_credit_reason="<cbc:InstructionNote>"+credit_reason+"</cbc:InstructionNote>"
		if not credit_against:
			warnings.append({"code":"Missing Credit Note Reference","message":"for a Credit note invoice, reference invoice is a required field."})
		credit_against="" if not credit_against else credit_against
		billing_reference="""
			<cac:BillingReference>
				<cac:InvoiceDocumentReference>
					<cbc:ID>{}</cbc:ID>
				</cac:InvoiceDocumentReference>
			</cac:BillingReference>
			""".format(credit_against)
	if debit_note:
		type_code="383"
		debit_against=d.reference
		debit_reason=d.debit_reason
		if not debit_reason:
			warnings.append({"code":"Missing Debit Note Reason","message":"for a Debit note invoice, debit_reason is a required field."})
			debit_credit_reason="<cbc:InstructionNote>test</cbc:InstructionNote>"
		else:
			debit_credit_reason="<cbc:InstructionNote>"+debit_reason+"</cbc:InstructionNote>"
		if not debit_against:
			warnings.append({"code":"Missing Credit Note Reference","message":"for a Credit note invoice, reference invoice is a required field."})
		debit_against="" if not debit_against else debit_against
		billing_reference="""
			<cac:BillingReference>
				<cac:InvoiceDocumentReference>
					<cbc:ID>{}</cbc:ID>
				</cac:InvoiceDocumentReference>
			</cac:BillingReference>
			""".format(debit_against)
		
		
	cr=d.cr_number
	scheme=d.scheme or "Commercial Registration number"
	schemes={"Commercial Registration number":"CRN","MOMRAH license":"MOM","MHRSD license":"MLS","700 Number":"700","MISA license":"SAG","Other OD":"OTH"}
	scheme=schemes[scheme]
	issue_date=d.issue_date
	issue_time=d.issue_time
	
	pih=d.pih or "-"
	country_code=d.country_code or "SA"
	payment_means=d.payment_means or "10"
	invoice_id=d.id
	uuid=d.uuid
	currency=d.currency or "SAR"
	tax_currency=d.tax_currenct or "SAR"
	delivery_date=d.delivery_date or ""
	delivery_date="""<cac:Delivery>
    	<cbc:ActualDeliveryDate>{0}</cbc:ActualDeliveryDate>
    </cac:Delivery>""".format(delivery_date) if delivery_date else """<cac:Delivery>
    	<cbc:ActualDeliveryDate>{0}</cbc:ActualDeliveryDate>
    </cac:Delivery>""".format(issue_date)
	net_total=float(d.net_total)
	total_discount=float(d.total_discount) if d.total_discount else 0
	taxable_amount=float(d.taxable_amount)
	total_advance=float(d.total_advance) if d.total_advance else 0
	grand_total=float(d.grand_total)
	
	tax_amount=d.tax_amount
	
	
	
	supplier=d.supplier
	customer=d.customer
	company_name=supplier["name"]
	tax_id=supplier["tax_id"]
	try:
		customer_name=customer["name"] or "Guest"
	except:
		customer_name="Guest"
	if "street_name" in supplier.keys():
		company_street_name=supplier["street_name"] or ""
	else:
		company_street_name=""
	if "building_number" in supplier.keys():
		company_building_number = str(supplier["building_number"]) or ""
	else:
		company_building_number=""
	if "plot" in supplier.keys():
		company_plot = supplier["plot"] or ""
	else:
		company_plot=""
	if "city" in supplier.keys():
		company_city = supplier["city"] or ""
	else:
		company_city=""
	if "postal_code" in supplier.keys():
		company_postal_code = supplier["postal_code"] or ""
	else:
		company_postal_code=""
	if "subdivision" in supplier.keys():
		company_subdivision = supplier["subdivision"] or ""
	else:
		company_subdivision=""
		
	if "street_name" in customer.keys():
		customer_street_name=customer["street_name"] or ""
	else:
		customer_street_name=""
	if "building_number" in customer.keys():
		customer_building_number = customer["building_number"] or ""
	else:
		customer_building_number=""
	if "plot" in customer.keys():
		customer_plot = customer["plot"] or ""
	else:
		customer_plot=""
	if "city" in customer.keys():
		customer_city = customer["city"] or ""
	else:
		customer_city=""
	if "postal_code" in customer.keys():
		customer_postal_code = customer["postal_code"] or ""
	else:
		customer_postal_code=""
	if "subdivision" in customer.keys():
		customer_subdivision = customer["subdivision"] or ""
	else:
		customer_subdivision=""
	if "tax_id" in customer.keys():
		customer_tax_id = str(customer["tax_id"]) or ""
	else:
		customer_tax_id=""	
	customer_schemeid= ""
	if "schemeid" in customer.keys():
		customer_schemeid=str(customer["schemeid"]) or ""
	customer_id= ""
	if "customer_id" in customer.keys():
		customer_id=str(customer["customer_id"]) or ""
	taxable=0
	subtax="""<cac:TaxSubtotal>
            <cbc:TaxableAmount currencyID="SAR">{taxable_amount_}</cbc:TaxableAmount>
            <cbc:TaxAmount currencyID="SAR">{tax_amount}</cbc:TaxAmount>
             <cac:TaxCategory>
                 <cbc:ID >{tax_category}</cbc:ID>
                 <cbc:Percent>{vat_percent}</cbc:Percent>
                 {tax_code}
            	 {tax_reason}
                <cac:TaxScheme>
                   <cbc:ID >VAT</cbc:ID>
                </cac:TaxScheme>
             </cac:TaxCategory>
        </cac:TaxSubtotal>"""
	tax15=0
	taxes15=0
	taxzero=0
	subtaxes=""
	zero=0
	zerocode=""
	exempt=0
	exemptcode=""
	items=d.itemlines
	for i in items:
		if i["tax_rate"]!=0:
			taxable+=i["net_amount"]
		if i["tax_rate"]==15:
			tax15+=i["net_amount"]
			taxes15+=i["tax_amount"]
	if tax15:
			new=subtax.replace("{tax_category}","S").replace("{vat_percent}","15.00").replace("{taxable_amount_}",str(tax15)).replace("{tax_amount}",num(taxes15)).replace("{tax_code}","").replace("{tax_reason}","")
			subtaxes+=new
		
	replace={"{id}":invoice_id,"{uuid}":uuid,"{issue_date}":issue_date,"{issue_time}":issue_time,"{currency}":currency,"{pih}":pih,"{tax_currency}":tax_currency,
	"{company_tax_id}":tax_id,"{company_name}":company_name,"{scheme_type}":scheme,"{scheme_id}":cr,"{type_code}":type_code,"{type_code_name}":type_code_name,
	"{total_discount}":num(total_discount),"{total_advance}":num(total_advance),"{billing_reference}":billing_reference,"{debit_credit_reason}":debit_credit_reason,
	"{total_amount}":num(grand_total),"{taxable_amount}":num(taxable_amount),"{total}":num(net_total),"{payable_amount}":num(grand_total-total_advance),"{vat_percent}":tax_rate,"{base_tax_amount}":num(tax_amount),
	"{tax_category}":tax_category,"{tax_amount}":num(tax_amount),"{pih}":pih,"{tax_code}":tax_code,"{tax_reason}":tax_reason,"{payment_means}":payment_means,
	"{delivery_date}":delivery_date,"{country_code}":country_code,"{street_name}":company_street_name,"{building_number}":company_building_number,"{plot}":company_plot,
	"{city_name}":company_city,"{postal_code}":company_postal_code,"{city_subdivision}":company_subdivision,"{subtax}":subtaxes,"{rounding_amount}":"0.00"
			
			
		}
	replace["{customer_name}"]=customer_name
	replace["{customer_street_name}"]=customer_street_name or ""
	if customer_schemeid and customer_id:
		scheme="""<cac:PartyIdentification>
                <cbc:ID schemeID=\"{}\">{}</cbc:ID>
            </cac:PartyIdentification>""".format(customer_schemeid,customer_id)
		replace["{customer_scheme}\n"]=scheme
	else:
		replace["{customer_scheme}\n"]=""
	if typee.lower()=="standard":
		replace["{customer_tax_id}"]=customer_tax_id 
		replace["{customer_street_name}"]=customer_street_name or ""
		replace["{customer_building_number}"]=customer_building_number
		replace["{customer_plot}"]=customer_plot
		replace["{customer_city_subdivision}"]=customer_subdivision
		replace["{customer_city_name}"]=customer_city
		replace["{customer_postal_code}"]=customer_postal_code
			
			
	time=str(issue_time).replace(":","")[0:6]
	
	new_name=str(tax_id)+"_"+str(issue_date).replace("-","")+"T"+time+"_"+str(invoice_id)+".xml"
	lines=get_lines(items,tax_category)
	xml=xml.replace("{invoice_lines}",lines)
	xml=replaceAll(xml,replace)
	

	
	
	
	#invoice=xml
	rand="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))
	
	f=open(""+rand+".txt","w")
	f.write(replaceAll(xml,{"    {ext:UBLExtensions}\n":"","    {QR}\n":"","{cac:signature}":""}))
	f.close()
	cananolized_xml=cananolize(""+rand+".txt")
	hash_=get_hash(cananolized_xml)
	os.remove(""+rand+".txt")
	response={}
	
	#frappe.response["invoice"]=invoice
	if typee.lower()=="simple":
		xml,qr_str=sign(xml,company_name,tax_id,grand_total,tax_amount,issue_date,issue_time,d.certificate,d.private_key)
		if xml==False:
			response["http_status_code"]=400
			response["errors"]="Error decoding certificate or private key"
			response["warnings"]=[]
			return response
		if not xml:
			response["http_status_code"]=400
			response["errors"]="Server coul'd sign invoice"
			return
		response["qr_code"]=qr_str
			
	invoice=base64.b64encode(xml.encode("utf-8")).decode("utf-8")
	response["invoice"]=invoice
	response["hash"]=hash_
	
	response["file_name"]=new_name
	response["warnings"]=[]
	if len(warnings)>0:
		response["http_status_code"]=201
		response["warnings"]=warnings
	response["errors"]=[]
	response["http_status_code"]=200
	return response


def validate(d):
	errors=[]
	typee=d.invoice_type
	schemes={"Commercial Registration number":"CRN","MOMRAH license":"MOM","MHRSD license":"MLS","700 Number":"700","MISA license":"SAG","Other OD":"OTH"}
	if  not typee or  typee.lower() not in ["standard","simple"]:
		errors.append({"code":"Wrong Invoice Type","message":"invoice_type must be Standard or Simple"})
	else:
		if typee.lower()=="simple":
			if not d.certificate :
				errors.append({"code":"Missing Certificate","message":"For Simple sales invoice, certificate base64 encoded is a required field"})
			if not d.private_key:
				errors.append({"code":"Missing Private Key","message":"For Simple sales invoice, private_key base64 encoded is a required field"})
				
	if not d.id:
		errors.append({"code":"Missing Invoice id","message":"invoice id is a required field"})
	if not d.uuid:
		errors.append({"code":"Missing Invoice uuid","message":"invoice uuid is a required field"})
	else:
		if  not is_uuid(d.uuid):
			errors.append({"code":"Invalid Invoice uuid","message":"badly formed hexadecimal UUID string"})
	if not d.pih:
		errors.append({"code":"Missing Invoice pih","message":"invoice pih is a required field"})
	if not d.issue_date:
		errors.append({"code":"Missing Issue Date","message":"issue_date is a required field"})
	else:
		da=str(d.issue_date)
		if len(da)!=10 or not da[:4].isnumeric() or not da[5:7].isnumeric() or not da[8:].isnumeric() or da[4]!="-" or da[7]!="-":
			errors.append({"code":"Invalid Issue Date","message":"issue_date must be in format year-month-day"})
	if d.delivery_date:
		da=str(d.delivery_date)
		if len(da)!=10 or not da[:4].isnumeric() or not da[5:7].isnumeric() or not da[8:].isnumeric() or da[4]!="-" or da[7]!="-":
			errors.append({"code":"Invalid Delivery Date","message":"delivery_date must be in format year-month-day"})
	if not d.issue_time:
		errors.append({"code":"Missing Issue Time","message":"issue_time is a required field"})	
	taxes=d.tax_amount
	if taxes== None:
		errors.append({"code":"Missing Taxes","message":"tax_amount is a required field"})
	else:
		try:
			a=float(taxes)
			if a==0:
				if not d.tax_code:
					errors.append({"code":"Missing Tax Code","message":"For zero tax invoices, tax code is a required field"})
				if not d.tax_reason:
					errors.append({"code":"Missing Tax Reason","message":"For zero tax invoices, tax reason is a required field"})
		except:
			errors.append({"code":"Invalid Total taxes and charges","message":"tax_amount must be of type float"})
	credit_note=d.is_credit_note
	debit_note=d.is_debit_note
	if credit_note and credit_note not in [1,0,True,False]:
		errors.append({"code":"Invalid Credit Note","message":"credit_note must be a boolean type"})
	if debit_note and debit_note not in [1,0,True,False]:
		errors.append({"code":"Invalid Debit Note","message":"debit_note must be a boolean type"})
		
	if debit_note and credit_note:
		errors.append({"code":"Invalid","message":"Invoice cant not be both credit and debit note"})
	items=d.itemlines
	scheme=d.scheme
	if  scheme and scheme not in schemes.keys():
		errors.append({"code":"Invalid Scheme","message":"Scheme must be one of the folowwing list:Commercial Registration number,MOMRAH license,MHRSD license,700 Number,MISA license,Other OD. default : Commercial Registration number"})
	if not d.grand_total:
		errors.append({"code":"Missing Grand Total","message":"grand_total is a required field"})
	else:
		try:
			a=float(d.grand_total)
		except:
			errors.append({"code":"Invalid Grand Total","message":"grand_total must be of type float"})
	if not d.net_total:
		errors.append({"code":"Missing Net Total","message":"net_total is a required field"})
	else:
		try:
			a=float(d.net_total)
		except:
			errors.append({"code":"Invalid Net Total","message":"net_total must be of type float"})		
	if not d.taxable_amount:
		errors.append({"code":"Missing Taxable Amount","message":"taxable_amount is a required field"})
	else:
		try:
			a=float(d.taxable_amount)
		except:
			errors.append({"code":"Invalid Taxable Amount","message":"taxable_amount must be of type float"})	
	
				
	if  d.tax_rate == None:
		errors.append({"code":"Missing Tax Rate","message":"tax_rate is a required field"})
	else:
		try:
			a=float(d.tax_rate)
			if a !=15 and a!=0:
				errors.append({"code":"Invalid Tax Rate","message":"tax_rate must be 0 or 15"})
		except:
			errors.append({"code":"Invalid Tax Rate","message":"tax_rate must be 0 or 15"})
	try:
		
		items=d.itemlines
		for i in items:
			item_name=i["item_name"]
			qty=float(i["qty"])
			rate=float(i["rate"])
			tax=float(i["tax_amount"])
			net_amount=float(i["net_amount"])
			tax_rate=float(i["tax_rate"])
			total=float(i["grand_total"])
			
	except:
		errors.append({"code":"Invalid ItemLines","message":"Invoice itemlines are missing or invalid."})
	try:
		s=d.supplier
		n=s["name"]
		tax_id=str(s["tax_id"])
		if len(tax_id)!=15 or not tax_id.isnumeric() or tax_id[0]!="3" or tax_id[-1]!="3"  :
			errors.append({"code":"Invalid Supplier","message":"Supplier Tax id must be 15 digits, begins with 3 and ends with 3."})	
		
	except:
		errors.append({"code":"Invalid Supplier","message":"Supplier data are missing or invalid."})	
	if typee and typee.lower()=="standard":
		try:
			s=d.customer
			n=s["name"]
			try:
				if  d.tax_code not in ["VATEX-SA-HEA","VATEX-SA-EDU"]:
					tax_id=str(s["tax_id"])
					if tax_id and len(tax_id)!=15 or not tax_id.isnumeric() or tax_id[0]!="3" or tax_id[-1]!="3"  :
						errors.append({"code":"Invalid Customer","message":"Customer Tax id must be 15 digits, begins with 3 and ends with 3."})	
			except:
				pass		
		except:
			errors.append({"code":"Invalid Customer","message":"Customer data are missing or invalid."})	
	if d.tax_code and d.tax_code in ["VATEX-SA-HEA","VATEX-SA-EDU"]:
		try:
			scheme=d.customer["schemeid"]
			if scheme not in ["TIN","CRN","MOM","MLS","700","SAG","NAT","GCC","IQA","PAS","OTH"]:
				errors.append({"code":"Invalid Customer ID Scheme","message":"Customer Scheme id must be one of the folowing: TIN,CRN,MOM,MLS,700,SAG,NAT,IQA,PAS,Oth."})
			id_=d.customer["customer_id"]
			if not scheme or not id_:
				errors.append({"code":"Invalid Customer ID","message":"If tax code is VATEX-SA-HEA or VATEX-SA-EDU, customer scheme id and id are required"})
		except:
			errors.append({"code":"Invalid Customer ID","message":"If tax code is VATEX-SA-HEA or VATEX-SA-EDU, customer scheme id and id are required"})
	
	return errors

def get_lines(items,tax_category="S"):
	result=""
	f=open("assets/zatca/templates/item_line.xml","r")
	temp=f.read()
	f.close()
	item_id=1
	for i in items:
		if "discount" in i.keys() and i ["discount"]:
			discount=i["discount"]
		else:
			discount=0
		#tax=(i.tax_rate*i.base_amount)/100
		r=replaceAll(temp,{"{item_id}":item_id,"{qty}":num(i["qty"]),"{total}":num(i["net_amount"]),"{tax_amount}":num(i["tax_amount"]),
		"{grand_total}":num(i["grand_total"]),"{discount}":num(discount),
		"{tax_category}":tax_category,"{item_name}":i["item_name"],"{tax_percentage}":num(i["tax_rate"]),"{rate}":num(i["rate"])
		})
		result+=r
		item_id+=1
	if result[-1]=="\n":
		result=result[:-1]
	return result


def sign(invoice,company_name,tax_id,total,taxes,issue_date,issue_time,certificate,private_key):
	
	errors=[]
	try:
		certificate=base64.b64decode(certificate).decode("utf-8")
	except:
		return False
	try:
		private_key=base64.b64decode(private_key).decode("utf-8")
	except:
		return False
	if "-----BEGIN EC PRIVATE KEY-----" not in private_key:
		private_key="-----BEGIN EC PRIVATE KEY-----\n"+private_key+"\n-----END EC PRIVATE KEY-----"


	root = ET.fromstring(invoice)
	rand="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))
	#cananolized_xml=invoice.replace("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n","").replace("\n\n","\n")
	hf=open(rand+"xml_to_hash.xml","w")
	hf.write(replaceAll(invoice,{"    {ext:UBLExtensions}\n":"","    {QR}\n":"","{cac:signature}":""}))
	hf.close()
	cananolized_xml= cananolize(rand+"xml_to_hash.xml")
	os.remove(rand+"xml_to_hash.xml")
	xml_sha256=sha256(cananolized_xml.encode('utf-8')).hexdigest()
	hash_=base64.b64encode(bytes.fromhex(xml_sha256)).decode()
	f=open(rand+"hash.txt","wb+")
	f.write(base64.b64decode(hash_))
	f.close()
	f=open(rand+"key.pem","wb+")
	f.write(private_key.encode())
	f.close()
	
	sig=os.popen("openssl dgst -sha256 -sign "+rand+"key.pem "+rand+"hash.txt | base64 /dev/stdin").read()
	signature=str(sig).replace(" ","").replace("\n","")
	
	os.remove(rand+"key.pem")
	os.remove(rand+"hash.txt")
	certificate_sha256=sha256(certificate.encode('utf-8')).hexdigest()
	certificate_hash=base64.b64encode(certificate_sha256.encode("utf-8")).decode("utf-8")
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
		frappe.response["http_status_code"]=400
	signed_properties=""
	serial_number=str(serial_number)
	cet_isser=str(cert_issuer)
	signature_certificate_for_hash ='''<xades:SignedProperties xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" Id="xadesSignedProperties">\n                                    <xades:SignedSignatureProperties>\n                                        <xades:SigningTime>'''+sign_time+'''</xades:SigningTime>\n                                        <xades:SigningCertificate>\n                                            <xades:Cert>\n                                                <xades:CertDigest>\n                                                    <ds:DigestMethod xmlns:ds="http://www.w3.org/2000/09/xmldsig#" Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>\n                                                    <ds:DigestValue xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'''+str(certificate_hash) +'''</ds:DigestValue>\n                                                </xades:CertDigest>\n                                                <xades:IssuerSerial>\n                                                    <ds:X509IssuerName xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'''+cert_issuer+'''</ds:X509IssuerName>\n                                                    <ds:X509SerialNumber xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'''+serial_number+'''</ds:X509SerialNumber>\n                                                </xades:IssuerSerial>\n                                            </xades:Cert>\n                                        </xades:SigningCertificate>\n                                    </xades:SignedSignatureProperties>\n                                </xades:SignedProperties>'''
	sha_256_5 = sha256()
	sha_256_5.update(signature_certificate_for_hash.encode())
	signed_properties= base64.b64encode(sha_256_5.hexdigest().encode()).decode('UTF-8')
	extensions=read("assets/zatca/templates/extensions.xml")
	replace={"{hash}":hash_,"{signature}":signature,"{certificate}":certificate,"{certificate_hash}":certificate_hash,
		"{signing_time}":sign_time,"{issue_name}":cert_issuer,"{serial_number}":serial_number,
		"{signed_properties}":signed_properties
		}
	extensions=replaceAll(extensions,replace)
	#extensions = ET.fromstring(extensions)
	#root.insert(1,extensions)
	invoice=invoice.replace("\n    {ext:UBLExtensions}\n",extensions)
	
	timestamp=issue_date+"T"+issue_time #+"Z"
	public_key,tagnine=tag_nine(certificate)
	if not public_key or not tagnine:
		frappe.response["http_status_code"]=400
		return
	qr_str=qr_code(company_name,str(tax_id),timestamp,num(total),num(taxes),hash_,signature,public_key,tagnine)
	qr=read("assets/zatca/templates/qr_code.xml")
	qr=qr.replace("</cac:Signature>\n","</cac:Signature>")
	qr=qr.replace("{qr_code}",qr_str)
	invoice=invoice.replace("{QR}\n    ",qr)
	#invoice=invoice.replace("<cbc:ProfileID>",extensions+qr+"<cbc:ProfileID>")
	#encoded=base64.b64encode(invoice.encode("utf-8")).decode("utf-8")
	return invoice,qr_str
	
	
	
	
	
	
	
	
	
	
	
	
	
def get_hash(xml):
	xml_sha256=sha256(xml.encode('utf-8')).hexdigest()
	hash_=base64.b64encode(bytes.fromhex(xml_sha256)).decode()
	return hash_
	
	
def tag_nine(certificate):
	rand="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))
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
	os.remove("/tmp/"+rand+".pem")
	#getting signature algorith
	if cert_find > 0 and cert_find + 38 < len(cert):
		cert_sig_algo = cert[cert.rfind("Signature Algorithm: ecdsa-with-SHA256") + 38:].replace('\n', '')\
		.replace(':', '')\
		.replace(' ', '')
		return(zatca_cert_public_key,cert_sig_algo.replace("SignatureValue",""))
	else:
		return(None,None)
	
def replaceAll(txt,d):
	tmp_txt=txt
	for i in d:
		tmp_txt=tmp_txt.replace(i,str(d[i]))
	return(tmp_txt)
	
def read(file):
	try:
		f=open(file,"r")
		msg=f.read()
		f.close()
		return(msg)
	except:
		return(None)
def is_uuid(id_):
	try:
		new=UUID(id_,version=4)
	except:
		return False
	return str(new)==id_
	
def num(a):
	return("%.2f" % abs(float(a)))
def validate_email(email):  
	import re
	if re.match(r"[^@]+@[^@]+\.[^@]+", email):  
		return True  
	return False  
def get_urli(endpoint):
	if endpoint=="Developer Portal" or endpoint=="Developer":
		return("https://gw-apic-gov.gazt.gov.sa/e-invoicing/developer-portal")
	elif endpoint=="Simulation":
		return("https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation")
	else:
		return("https://gw-fatoora.zatca.gov.sa/e-invoicing/core")

def cananolize(xml_path):
	try:
		rando="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))
		et = ETT.parse(xml_path)
		et.write_c14n(rando+".xml",exclusive=0, with_comments=0)
		f=open(rando+".xml","r")
		cananolized_xml=f.read()
		f.close()
		os.remove(rando+".xml")
		return(cananolized_xml)
	except:
		return(None)
