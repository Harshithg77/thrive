
fetch("/chart-data")
.then(response => response.json())
.then(data => {
    const ctx = document.getElementById('habitChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [
                { label: 'Water', data: data.water, backgroundColor: 'rgba(54, 162, 235, 0.6)' },
                { label: 'Exercise', data: data.exercise, backgroundColor: 'rgba(255, 99, 132, 0.6)' },
                { label: 'Sleep', data: data.sleep, backgroundColor: 'rgba(255, 206, 86, 0.6)' },
                { label: 'Study', data: data.study, backgroundColor: 'rgba(75, 192, 192, 0.6)' }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'top' },
                title: { display: true, text: 'Habit Progress Last 7 Days' }
            },
            scales: { y: { beginAtZero: true } }
        }
    });
});
