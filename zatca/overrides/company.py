from erpnext.setup.doctype.company.company import Company
import frappe
from frappe import _
import os,base64,random
import OpenSSL.crypto
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from OpenSSL.crypto import load_certificate_request, FILETYPE_PEM

class CustomCompany(Company):

	@frappe.whitelist()
	def restart(self,values):
		if self.name!=values["company_name"]:
			alert("Company name does not match","red")
			return -1
		self.pih="NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ=="
		invoices=frappe.db.get_all("Sales Invoice",filters=[["company","in",[self.name]],["zatca_status",'in',["Cleared","Cleared with warnings","Reported","Reported with warnings","Rejected","Pending"]]],fields=["name","ksa_einv_qr","xml_path"])
		for i in invoices:
			if i["ksa_einv_qr"]:
				file_doc=frappe.get_all("File",{"file_url":i["ksa_einv_qr"]})
				if len(file_doc):
					frappe.delete_doc("File",file_doc[0]["name"])
			if i["xml_path"]:
				file_doc=frappe.get_all("File",{"file_url":i["xml_path"]})
				if len(file_doc):
					frappe.delete_doc("File",file_doc[0]["name"])
			frappe.db.set_value("Sales Invoice",i["name"],"zatca_status","Pending")
			frappe.db.set_value("Sales Invoice",i["name"],"hash","")
			frappe.db.set_value("Sales Invoice",i["name"],"custom_pih","")
			frappe.db.set_value("Sales Invoice",i["name"],"ksa_einv_qr","")
			frappe.db.set_value("Sales Invoice",i["name"],"custom_zatca_warnings","")
			frappe.db.set_value("Sales Invoice",i["name"],"custom_clearing_to_zatka_time",None)
			frappe.db.set_value("Sales Invoice",i["name"],"custom_reporting_to_zatka_time",None)
			frappe.db.set_value("Sales Invoice",i["name"],"xml_path","")
			frappe.db.set_value("Sales Invoice",i["name"],"qr_code_text","")
		self.pih="NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ=="
		alert("Invoices restarted")
		return "1"
	def tag_nine(self):
		rand="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))
		pcsid=self.pcsid_username
		if not pcsid:
			pcsid=frappe.db.get_value("Company",company,"ccsid_username")
		certificate=base64.b64decode(pcsid.encode("utf-8")).decode()
		#certificate = x509.load_pem_x509_certificate(cert.encode(), default_backend())
		sandbox=self.sandbox
		if "-----BEGIN CERTIFICATE-----\n" not in certificate:
			certificate = "-----BEGIN CERTIFICATE-----\n" + certificate + "\n-----END CERTIFICATE-----"
		f=open("/tmp/"+rand+".pem","w+")
		f.write(certificate)
		f.close()
		certificate_public_key = "openssl x509 -pubkey -noout -in /tmp/"+rand+".pem"
		zatca_cert_public_key = os.popen(certificate_public_key).read()
		zatca_cert_public_key = zatca_cert_public_key.replace('-----BEGIN PUBLIC KEY-----', '')\
									.replace('-----END PUBLIC KEY-----', '')\
									 .replace('\n', '').replace(' ', '')
		
		os_cmd="openssl x509 -in /tmp/"+rand+".pem -text -noout"
		cert=os.popen(os_cmd).read()
		cert_find = cert.rfind("Signature Algorithm: ecdsa-with-SHA256")
		os.remove("/tmp/"+rand+".pem")
		if cert_find > 0 and cert_find + 38 < len(cert):
			cert_sig_algo = cert[cert.rfind("Signature Algorithm: ecdsa-with-SHA256") + 38:].replace('\n', '')\
			.replace(':', '')\
			.replace(' ', '')
			return(zatca_cert_public_key,cert_sig_algo.replace("SignatureValue",""))
		else:
			return(None,None)

	def before_save(self):
		if self.custom_short_address:
			add=self.custom_short_address
			if len(add)!=8:
				frappe.throw(_("The short address must consists of 4 letters and 4 numbers.example : RRRD2929"))
			if not add[:4].isupper() or not add[4:].isnumeric():
				frappe.throw(_("The short address must consists of 4 letters and 4 numbers.example : RRRD2929"))
		if self.pcsid_username:
			key,sig=self.tag_nine()
			self.custom_cet_public_key=key
			self.custom_cert_sig_algo=sig
				
	@frappe.whitelist()
	def insert_csr(self,values):
		csr=values["csr"]
		if values["type"]=="Text":
			csr=base64.b64encode(csr.encode("utf-8")).decode()
		#csr=csr.replace("\n","")
		#csr=csr.replace("-----BEGIN CERTIFICATE-----","")
		#csr=csr.replace("-----END CERTIFICATE-----","")
		#csr=csr.replace("-----BEGIN CERTIFICATE REQUEST-----","")
		#csr=csr.replace("-----END CERTIFICATE REQUEST-----","")
		self.csr=csr
		if not self.pih or values["restart_pih"]:
			self.pih="NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ=="
		self.save()
		alert("CSR inserted.")
	@frappe.whitelist()
	def generate_csr(self,values):
		if "Zatca Manager" not in frappe.get_roles(frappe.session.user):
			frappe.throw(_("You don't have permissions to manage zatca settings, Contact administration."))
		title=validate(values)
		self.save_data(values)
		template_path="assets/zatca/zatca/template.cnf"
		cname="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))
		sim=False
		if self.custom_api_endpoint=="Simulation":
			sim=True
		try:
			f = open(template_path, "r")
			text=f.read()
			text=config(text,values,title,sim)
			name="assets/zatca/zatca/"+cname+"config.cnf"
			f=open(name,"w")
			f.write(text)
			f.close()
			#alert("Config file generated")
		except:
			alert("Error while creating config file","red")
			return(-1)
		if True:
			os.system("openssl ecparam -name secp256k1 -genkey -noout -out assets/zatca/zatca/"+cname+"privatekey.pem")
			pk=open("assets/zatca/zatca/"+cname+"privatekey.pem","r")
			a=pk.read()
			#a=a.replace("-----BEGIN EC PRIVATE KEY-----","")			
			#a=a.replace("-----END EC PRIVATE KEY-----","")
			#a=a.replace("\n","")
			#a=a.replace("\t","")
			self.private_key=a
			#new_pk=open("assets/zatca/zatca-sdk/Data/Certificates/ec-secp256k1-priv-key.pem","w")
			#new_pk.write(a)
			pk.close()
			#new_pk.close()
			#alert("Private key generated")
		else:
			alert("Error while creating private key","red")
			return(-1)
		try:
			os.system("openssl ec -in assets/zatca/zatca/"+cname+"privatekey.pem -pubout -conv_form compressed -out assets/zatca/zatca/"+cname+"publickey.pem")
			#alert("Public key generated")
		except:
			alert("Error while creating public key","red")
			return(-1)
		try:
			a=os.popen("openssl base64 -d -in assets/zatca/zatca/"+cname+"publickey.pem -out assets/zatca/zatca/"+cname+"publickey.bin").read()
			
		except:
			alert("Error while creating bin file","red")
			return(-1)
		try:
			a=os.popen("openssl req -new -sha256 -key assets/zatca/zatca/"+cname+"privatekey.pem -extensions v3_req -utf8 -config assets/zatca/zatca/"+cname+"config.cnf -out assets/zatca/zatca/"+cname+"csr.csr").read()

			os.system("openssl base64 -in assets/zatca/zatca/"+cname+"csr.csr -out assets/zatca/zatca/"+cname+"csr.txt")
			alert(_("CSR file generated successfully"))
		except:
			alert("Error while generating CSR file")
		f=open("assets/zatca/zatca/"+cname+"csr.txt","r")
		csr=f.read()
		csr=csr.replace("\n","")
		self.csr=csr
		if not self.pih or values["restart_pih"]:
			self.pih="NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ=="
		os.remove(name)
		os.remove("assets/zatca/zatca/"+cname+"csr.csr")
		os.remove("assets/zatca/zatca/"+cname+"csr.txt")
		os.remove("assets/zatca/zatca/"+cname+"publickey.pem")
		os.remove("assets/zatca/zatca/"+cname+"publickey.bin")
		os.remove("assets/zatca/zatca/"+cname+"privatekey.pem")
		self.save()
		return("1")



	def save_data(self,v):
		changed=False
		if self.sn!=v["sn"]:
			self.sn=v["sn"]
			changed=True
		if self.ou!=v["ou"]:
			self.ou=v["ou"]
			changed=True
		if self.cn!=v["cn"]:
			self.cn=v["cn"]
			changed=True
		if self.t!=v["t"]:
			self.t=v["t"]
			changed=True
		if self.s!=v["s"]:
			self.s=v["s"]
			changed=True
		if "c" in v.keys() and self.c!= v["c"]:
			self.c=v["c"]
			changed=True
		if "z" in v.keys() and self.z!=v["z"]:
			self.z=v["z"]
			changed=True
		if self.tax_id!=v["uid"]:
			self.tax_id=v["uid"]
			changed=True
		if self.email!=v["email"]:
			self.email=v["email"]
			changed=True
		if self.domain!=v["businessCategory"]:
			self.domain=v["businessCategory"]
			changed=True
		if self.custom_short_address!=v["registredAddress"]:
			self.custom_short_address=v["registredAddress"]
			changed=True
		if changed:
			self.save()
			#alert("Saved")

def validate(values):
	if "sn" not in values.keys() or  not values["sn"]:
		error("Serial number is missing")
	if "ou" not in values.keys() or  not values["ou"]:
		error("Organization Unit Name is missing")
	if "o" not in values.keys() or  not values["o"]:
		error("Company name is missing")
	if "uid" not in values.keys() or  not values["uid"]:
		error("Organization identifier is missing")
	tax_id=str(values["uid"])
	if len(tax_id)!=15 or not tax_id.isnumeric() or tax_id[0]!="3" or tax_id[-1]!="3"  :
		error("Tax id must be 15 digits, begins with 3 and ends with 3.")
	
	if tax_id[10]=="1":
		ou=str(values["ou"])
		if len(ou)!=10 or not ou.isnumeric():
			error("In case of VAT Groups, organization unit name must be a 10-digits TIN.")
	if  not values["uid"].isnumeric() or len(values["uid"])!=15:
		error("Organization identifier should contain 15 digits.")
	if "cn" not in values.keys() or  not values["cn"]:
		error("Common name is missing")
	if "email" not in values.keys() or not values["email"]:
		error("Company email is missing")
	if "registredAddress" not in values.keys() or  not values["registredAddress"]:
		error("Company address is missing")
	if "businessCategory" not in values.keys() or  not values["businessCategory"]:
		error("Business Category is missing")
	title=""
	t="1" if values["t"] else "0"
	s="1" if values["s"] else "0"
	c="1" if "c" in values.keys() and values["c"] else "0"
	z="1" if "z" in values.keys() and values["z"] else "0"
	title=t+s+c+z
	return(title)




def config(text,v,title,sim):
	certificate_template="ASN1:PRINTABLESTRING:ZATCA-Code-Signing"
	if sim:
		certificate_template="ASN1:PRINTABLESTRING:PREZATCA-Code-Signing"
	a=text.replace("{title}",title)
	a=a.replace("{c}",v["cc"])
	a=a.replace("{ou}",v["ou"])
	a=a.replace("{o}",v["o"])
	a=a.replace("{cn}",v["cn"])
	a=a.replace("{sn}",v["sn"])
	a=a.replace("{uid}",v["uid"])
	a=a.replace("{address}",v["registredAddress"])
	a=a.replace("{category}",v["businessCategory"])
	a=a.replace("{email}",v["email"])
	a=a.replace("{certificate_template}",certificate_template)
	return(a)
def error(msg):
	frappe.throw(title=_("Error"),msg=_(msg))
def alert(msg,color="green"):
	frappe.msgprint(
		_(msg),
		alert=True,
		indicator=color
	)
