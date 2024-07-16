import frappe
import base64
import binascii
def qr_code(name,tax_id,datetime,total,vat_total,hash,signature,key,ecdsa=None,simple=True):
        #frappe.throw(ecdsa)
        def get_qr_encoding(tag, field):
            company_name_byte_array = field if tag in [8, 9] else field.encode()
            company_name_tag_encoding = tag.to_bytes(length=1, byteorder='big')
            company_name_length_encoding = len(company_name_byte_array).to_bytes(length=1, byteorder='big')
            return company_name_tag_encoding + company_name_length_encoding + company_name_byte_array
        if 1:
            qr_code_str = ''
            if 1:
                seller_name_enc = get_qr_encoding(1, name)
                company_vat_enc = get_qr_encoding(2, tax_id)
                timestamp_enc = get_qr_encoding(3,datetime)
                # invoice_total_enc = get_qr_encoding(4, float_repr(abs(record.amount_total_signed), 2))
                invoice_total_enc = get_qr_encoding(4, str(total))
                # total_vat_enc = get_qr_encoding(5, float_repr(abs(record.amount_tax_signed), 2))
                total_vat_enc = get_qr_encoding(5, str(vat_total))
                invoice_hash = get_qr_encoding(6,hash)
                ecdsa_signature = get_qr_encoding(7, signature)
                cert_pub_key = base64.b64decode(key)
                ecdsa_public_key = get_qr_encoding(8, cert_pub_key)
                if simple:
                    ecdsa_cert_value = get_qr_encoding(9, binascii.unhexlify(ecdsa))

                str_to_encode = seller_name_enc + company_vat_enc + timestamp_enc + invoice_total_enc + total_vat_enc
                str_to_encode += invoice_hash + ecdsa_signature + ecdsa_public_key
                if simple:
                    str_to_encode += ecdsa_cert_value
                qr_code_str = base64.b64encode(str_to_encode).decode()
        return(qr_code_str)
