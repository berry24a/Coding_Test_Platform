document.getElementById('submission-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const code = document.getElementById('code').value;

    fetch('/submit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username: username,
            password: password,
            code: code
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Success:', data);
        alert('Code submitted successfully! ID: ' + data.id);
    })
    .catch((error) => {
        console.error('Error:', error);
        alert('Failed to submit code');
    });
});
