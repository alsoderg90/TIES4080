"use strict";  
//@ts-check 

window.onload = function() {
	let team = document.getElementsByClassName("team")[0]
	team.addEventListener("click", show);
	let teams = document.getElementsByClassName("teams")[0]
	teams.addEventListener("click", show);
	
	
	function show(e) {
		//piilotetaan kaikki
		let tabcontent = document.getElementsByClassName("tabcontent");		
		for (let i = 0; i < tabcontent.length; i++) {
			tabcontent[i].style.display = "none";
			console.log(tabcontent[i].previousElementSibling);
			tabcontent[i].previousElementSibling.id = "inactive";
		}
		//näkyväksi valittu
		document.getElementById(e.target.className).style.display = "block";
		e.currentTarget.id = "active";
	}

}