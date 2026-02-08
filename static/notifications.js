// Student Notification System
// Include this script in any student-facing page to receive real-time notifications

(function () {
    let notificationCheckInterval = null;

    function checkNotifications() {
        fetch('/api/notifications')
            .then(res => res.json())
            .then(data => {
                if (data.notifications && data.notifications.length > 0) {
                    data.notifications.forEach(notif => {
                        showNotification(notif);
                    });
                }
            })
            .catch(err => console.error('Notification fetch error:', err));
    }

    function showNotification(notif) {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `notification-toast ${notif.type}`;
        toast.innerHTML = `
            <div class="notification-header">
                <span class="notification-sender">${notif.sender_name}</span>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            <div class="notification-message">${notif.message}</div>
        `;

        document.body.appendChild(toast);

        // Mark as read
        fetch(`/api/notifications/${notif.id}/mark_read`, { method: 'POST' })
            .catch(err => console.error('Mark read error:', err));

        // Auto-remove after 8 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 8000);
    }

    // Check immediately on load
    setTimeout(checkNotifications, 2000);

    // Then check every 30 seconds
    notificationCheckInterval = setInterval(checkNotifications, 30000);
})();
