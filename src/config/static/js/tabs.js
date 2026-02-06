/**
 * Tab switching logic.
 */

function switchTab(tabName, btn) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabName).classList.add('active');
    if (btn) btn.classList.add('active');
    if (tabName === 'menu') {
        generateWeekPlanner();
    }
}
