// Chart.js CDN loader for dashboard analytics
// Add a bar chart for transactions and a doughnut for balance breakdown

document.addEventListener('DOMContentLoaded', function() {
  // Transaction Bar Chart
  if (document.getElementById('transactionsChart')) {
    const ctx = document.getElementById('transactionsChart').getContext('2d');
    new Chart(ctx, {
      type: 'bar',
      data: window.transactionsChartData,
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          title: { display: true, text: 'Last 6 Transactions' }
        },
        scales: {
          y: { beginAtZero: true }
        }
      }
    });
  }
  // Balance Doughnut Chart
  if (document.getElementById('balanceChart')) {
    const ctx2 = document.getElementById('balanceChart').getContext('2d');
    new Chart(ctx2, {
      type: 'doughnut',
      data: window.balanceChartData,
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'bottom' },
          title: { display: true, text: 'Balance Breakdown' }
        }
      }
    });
  }
});
