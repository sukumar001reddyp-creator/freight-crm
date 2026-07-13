document.addEventListener("DOMContentLoaded", function () {

    const canvas = document.getElementById("reportChart");

    if (!canvas) return;

    new Chart(canvas, {
        type: "bar",

        data: {

            labels: [
                "Clients",
                "Enquiries",
                "Quotations",
                "Shipments",
                "Active Clients",
                "Pending Enquiries",
                "Approved Quotes",
                "Support Tickets"
            ],

            datasets: [{

                label: "CRM Summary",

                data: [

                    Number(document.querySelectorAll(".report-card h2")[0].innerText),
                    Number(document.querySelectorAll(".report-card h2")[1].innerText),
                    Number(document.querySelectorAll(".report-card h2")[2].innerText),
                    Number(document.querySelectorAll(".report-card h2")[3].innerText),
                    Number(document.querySelectorAll(".report-card h2")[4].innerText),
                    Number(document.querySelectorAll(".report-card h2")[5].innerText),
                    Number(document.querySelectorAll(".report-card h2")[6].innerText),
                    Number(document.querySelectorAll(".report-card h2")[7].innerText)

                ],

                backgroundColor: [
                    "#2563eb",
                    "#0ea5e9",
                    "#16a34a",
                    "#7c3aed",
                    "#059669",
                    "#ea580c",
                    "#0891b2",
                    "#dc2626"
                ],

                borderRadius: 8

            }]

        },

        options: {

            responsive: true,

            plugins: {

                legend: {
                    display: false
                }

            },

            scales: {

                y: {
                    beginAtZero: true
                }

            }

        }

    });

});
const monthlyCanvas =
document.getElementById("monthlyChart");

if(monthlyCanvas){

    new Chart(monthlyCanvas,{

        type:"line",

        data:{

            labels:[
                "Jan","Feb","Mar","Apr",
                "May","Jun","Jul","Aug",
                "Sep","Oct","Nov","Dec"
            ],

            datasets:[

                {

                    label:"Clients",

                    data:window.monthlyClients,

                    borderColor:"#2563eb",

                    fill:false

                },

                {

                    label:"Enquiries",

                    data:window.monthlyEnquiries,

                    borderColor:"#16a34a",

                    fill:false

                },

                {

                    label:"Shipments",

                    data:window.monthlyShipments,

                    borderColor:"#dc2626",

                    fill:false

                },

                {

                    label:"Quotations",

                    data:window.monthlyQuotations,

                    borderColor:"#7c3aed",

                    fill:false

                }

            ]

        },

        options:{

            responsive:true

        }

    });

}