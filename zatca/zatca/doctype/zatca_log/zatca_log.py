# Copyright (c) 2023, Weslati Baha Eddine and contributors
# For license information, please see license.txt

import frappe,base64,json
from frappe import _ 
import xml.etree.ElementTree as ET
import xmltodict



from frappe.model.document import Document

class ZatcaLog(Document):
	
	
	
	@frappe.whitelist()
	def fetch(self):
		xml=self.xml
		xml=base64.b64decode(xml).decode("utf-8")
		data=xmltodict.parse(xml)
		data=json.dumps(data)
		data=json.loads(data)
		print(data["Invoice"]["cbc:ID"])
		
		
		root=ET.fromstring(xml)
		for child in root:
			#print(child.tag,child.attrib)
			pass
		id_ =data["Invoice"]["cbc:ID"]
		date=root.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}IssueDate").text
		money=root.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}LegalMonetaryTotal")
		tax_exclu=money.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxExclusiveAmount").text
		tax_inclu=money.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxInclusiveAmount").text
		tax=root.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxTotal")
		tax=tax.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxAmount").text
		supplier=root.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AccountingSupplierParty")
		party=supplier.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Party")

		company=party.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyLegalEntity")
		company=company.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}RegistrationName").text
		tax_id=party.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyTaxScheme")

		tax_id=tax_id.find("{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}CompanyID").text
		msg=""
		msg+="Company : " + company + "<br>"
		msg+="Tax id  : " + tax_id + "<br>"
		msg+="Date : " + date + "<br>"
		msg+="Id : " + id_ + "<br>"
		msg+="Total Taxes : " + tax + "<br>"
		frappe.msgprint(msg)
