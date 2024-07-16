// Copyright (c) 2023, Weslati Baha Eddine and contributors
// For license information, please see license.txt

frappe.ui.form.on('Zatca Log', {
	refresh: function(frm) {
	
	frm.add_custom_button(__("Fetch Data"), function() {
					frappe.call({
					method:"fetch",
					doc:frm.doc,
					callback(r){
						if (r.message){
							
						}
					}
				})
					
					
				});
				
				

	}
});
