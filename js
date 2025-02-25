     async function updateTable() {
       try {
            const response = await fetch('/update_table');
          const data = await response.json();
                
                const table = document.getElementById('dataTable');
                const thead = table.querySelector('thead');
                const tbody = table.querySelector('tbody');
        
                if (data.length > 0) {
                    const headers = Object.keys(data[0]);
                    thead.innerHTML = `<tr>${headers.map(header => `<th>${header}</th>`).join('')}</tr>`;
                }
        
                tbody.innerHTML = data.map(row => `<tr>${Object.values(row).map(value => `<td>${value}</td>`).join('')}</tr>`).join('');
            } catch (error) {
                console.error('Error fetching table data:', error);
                alert('Error fetching table data');
            }
    } 