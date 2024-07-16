// Copyright (c) 2023, Weslati Baha Eddine and contributors
// For license information, please see license.txt

frappe.ui.form.on("Zatca Auth", {
	refresh(frm) {
		if (frm.doc.key && frm.doc.secret){
			frm.add_custom_button(__("Copy token"), function() {
				navigator.clipboard.writeText(frm.doc.key+":"+frm.doc.secret);
				frappe.show_alert({"message":__("Copied to clipboard."),"indicator":"green"})

			})
		}
 	},
});
