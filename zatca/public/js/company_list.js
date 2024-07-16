frappe.listview_settings['Company'] = {
	add_fields: ["custom_api_endpoint"],
	formatters:{
		custom_zatca_status(val,field,doc){
			if (doc.custom_zatca_status=="Enabled"){
                                return "<span class='indicator-pill green'>"+__(doc.custom_api_endpoint)+"</span>"
                        }
                        if (doc.custom_zatca_status=="Disabled"){
                                return "<span class='indicator-pill red'>"+__(val)+"</span>"
                        }
		}
	}
}
