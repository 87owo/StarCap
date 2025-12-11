import os, math, time, random, logging
from flask import Flask, jsonify, session, request, render_template_string
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.secret_key = os.urandom(32)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CaptchaDemo")

def generate_char_data():
    char = chr(random.randint(65, 90))
    img_size = 100
    font_size = 80
    img = Image.new('L', (img_size, img_size), 0)
    draw = ImageDraw.Draw(img)
    
    font = None
    possible_fonts = [
        "arial.ttf", "Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arial.ttf"
    ]
    
    for font_path in possible_fonts:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except OSError:
            continue
            
    if font is None:
        try:
            font = ImageFont.load_default(size=font_size)
        except TypeError:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), char, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (img_size - text_w) // 2
    y = (img_size - text_h) // 2 - 12
    draw.text((x, y), char, font=font, fill=255)
    
    pixels = []
    width, height = img.size
    data = img.load()
    
    target_x = random.uniform(50.0, 80.0) * (1 if random.random() > 0.5 else -1)
    target_y = random.uniform(50.0, 80.0) * (1 if random.random() > 0.5 else -1)
    
    for py in range(height):
        for px in range(width):
            if data[px, py] > 128:
                vx = random.uniform(-0.8, 0.8)
                vy = random.uniform(-0.8, 0.8)
                shifted_x = px + vx * target_x
                shifted_y = py + vy * target_y
                pixels.append({'x': shifted_x, 'y': shifted_y, 'vx': vx, 'vy': vy})
                
    return {'char': char, 'pixels': pixels, 'target_x': target_x, 'target_y': target_y}

@app.route('/api/captcha/get', methods=['POST'])
def get_captcha():
    data = generate_char_data()
    session['captcha_target'] = {
        'x': data['target_x'],
        'y': data['target_y'],
        'char': data['char'],
        'start_time': time.time()
    }
    return jsonify({
        'pixels': data['pixels'],
        'canvas_size': 400
    })

@app.route('/api/captcha/verify', methods=['POST'])
def verify_captcha():
    if 'captcha_target' not in session:
        return jsonify({'status': 'fail', 'msg': 'Session expired'})
        
    req_data = request.json
    final_x = req_data.get('x')
    final_y = req_data.get('y')
    trajectory = req_data.get('trajectory', [])
    target = session['captcha_target']
    
    dist = math.sqrt((final_x - target['x'])**2 + (final_y - target['y'])**2)

    if len(trajectory) < 20:
        return jsonify({'status': 'fail', 'msg': 'Unnatural movement'})
    elif dist > 10 and dist <= 20:
        return jsonify({'status': 'fail', 'msg': 'Not accurate enough'})
    elif dist > 20:
        return jsonify({'status': 'fail', 'msg': 'Incorrect position'})

    speeds = []
    for i in range(1, len(trajectory)):
        p1 = trajectory[i-1]
        p2 = trajectory[i]
        dt = p2['t'] - p1['t']
        if dt > 0:
            dx = p2['x'] - p1['x']
            dy = p2['y'] - p1['y']
            speed = math.sqrt(dx**2 + dy**2) / dt
            speeds.append(speed)
            
    if not speeds:
        return jsonify({'status': 'fail', 'msg': 'Movement abnormal'})
        
    avg_speed = sum(speeds) / len(speeds)
    if avg_speed > 1:
        return jsonify({'status': 'fail', 'msg': 'Movement too fast'})
        
    session.pop('captcha_target', None)
    return jsonify({'status': 'success', 'msg': f'Verification successful! Character: {target["char"]}'})

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PYAS Captcha Demo</title>
    <style>
        :root { --primary: #007aff; --bg: #f5f5f7; --card: #ffffff; --text: #111111; --green: #008000; --red: #ff3b30; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        
        .btn { background: var(--primary); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 16px; transition: 0.2s; }
        .btn:hover { opacity: 0.9; }
        .btn-outline { background: transparent; border: 1px solid var(--primary); color: var(--primary); }

        .captcha-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.6);
            backdrop-filter: blur(5px);
            z-index: 10000;
            display: none;
            justify-content: center;
            align-items: center;
        }
        .captcha-box {
            background: var(--card);
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
            text-align: center;
            max-width: 440px;
            width: 90%;
        }
        .captcha-canvas-container {
            position: relative;
            width: 400px;
            height: 400px;
            margin: 0 auto;
            background: #000;
            border-radius: 8px;
            overflow: hidden;
            cursor: grab;
            touch-action: none;
        }
        .captcha-canvas-container:active { cursor: grabbing; }
        .captcha-instruction { margin-top: 15px; color: #666; font-size: 14px; }
        #captchaStatus { margin: 10px 0; font-weight: bold; height: 20px; font-size: 14px; }
        .status-success { color: var(--green); }
        .status-fail { color: var(--red); }
        .copyright { margin-top: 20px; font-size: 12px; color: #999; }
    </style>
</head>
<body>

    <div style="text-align: center;">
        <h1>PYAS Star Captcha Demo</h1>
        <p>Click the button below to start the verification process</p>
        <button class="btn" onclick="openCaptcha()">Start Human Verification</button>
    </div>

    <div class="captcha-overlay" id="captchaOverlay">
        <div class="captcha-box">
            <h3 style="margin-top:0">Security Verification</h3>
            <div class="captcha-canvas-container" id="captchaContainer">
                <canvas id="captchaCanvas" width="400" height="400"></canvas>
            </div>
            <div class="captcha-instruction">Please drag/slide the screen until the hidden character is visible.<br>Release to verify.</div>
            <div id="captchaStatus"></div>
            <button class="btn btn-outline" onclick="loadCaptcha()" style="margin-top:15px; width: 400px; font-size: 14px; padding: 10px 0;">Refresh Challenge</button>
            <button class="btn btn-outline" onclick="closeCaptcha()" style="margin-top:10px; width: 400px; font-size: 14px; padding: 10px 0; border-color: #999; color: #666;">Close</button>
        </div>
    </div>
    
    <div class="copyright">
        © 2020-2026 87owo (StarCap). All rights reserved. The project is from <a href="https://github.com/87owo/StarCap" target="_blank" style="color: inherit;">https://github.com/87owo/StarCap</a>
    </div>

<script>
    const captchaOverlay = document.getElementById('captchaOverlay');
    const captchaCanvas = document.getElementById('captchaCanvas');
    const captchaCtx = captchaCanvas.getContext('2d');
    const captchaContainer = document.getElementById('captchaContainer');
    const captchaStatus = document.getElementById('captchaStatus');
    
    let captchaPixels = [];
    let isCaptDragging = false;
    let startX = 0, startY = 0;
    let currentX = 0, currentY = 0;
    let captTrajectory = [];

    function openCaptcha() {
        captchaOverlay.style.display = 'flex';
        loadCaptcha();
    }

    function closeCaptcha() {
        captchaOverlay.style.display = 'none';
    }

    function loadCaptcha() {
        captchaStatus.textContent = 'Loading...';
        captchaStatus.className = '';
        fetch('/api/captcha/get', { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                captchaPixels = data.pixels;
                currentX = 0; currentY = 0; 
                startX = 0; startY = 0; 
                captTrajectory = [];
                captchaStatus.textContent = '';
                renderCaptcha();
            })
            .catch(e => {
                captchaStatus.textContent = 'Loading failed';
                captchaStatus.className = 'status-fail';
            });
    }

    function renderCaptcha() {
        captchaCtx.fillStyle = '#000';
        captchaCtx.fillRect(0, 0, captchaCanvas.width, captchaCanvas.height);
        
        const cx = captchaCanvas.width / 2;
        const cy = captchaCanvas.height / 2;
        
        captchaCtx.fillStyle = '#0f0';
        
        captchaPixels.forEach(p => {
            const computedX = p.x - (p.vx * currentX);
            const computedY = p.y - (p.vy * currentY);
            
            const finalX = (computedX * 3) + (cx - 150); 
            const finalY = (computedY * 3) + (cy - 150);
            
            captchaCtx.beginPath();
            captchaCtx.arc(finalX, finalY, 1.5, 0, Math.PI * 2);
            captchaCtx.fill();
        });
    }

    function verifyCaptcha() {
        captchaStatus.textContent = 'Verifying...';
        fetch('/api/captcha/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x: currentX, y: currentY, trajectory: captTrajectory })
        })
        .then(r => r.json())
        .then(data => {
            captchaStatus.textContent = data.msg;
            captchaStatus.className = data.status === 'success' ? 'status-success' : 'status-fail';
            if (data.status === 'success') {
                setTimeout(() => {
                    alert("Verification successful!");
                    closeCaptcha();
                }, 500);
            } else {
                setTimeout(loadCaptcha, 1500);
            }
        });
    }

    captchaContainer.addEventListener('mousedown', e => { 
        isCaptDragging = true; 
        startX = e.clientX - currentX; 
        startY = e.clientY - currentY; 
        captTrajectory = []; 
    });
    
    window.addEventListener('mouseup', e => { 
        if (!isCaptDragging) return; 
        isCaptDragging = false; 
        verifyCaptcha(); 
    });
    
    window.addEventListener('mousemove', e => {
        if (!isCaptDragging) return;
        currentX = e.clientX - startX; 
        currentY = e.clientY - startY;
        captTrajectory.push({ x: currentX, y: currentY, t: Date.now() });
        renderCaptcha();
    });

    captchaContainer.addEventListener('touchstart', e => { 
        isCaptDragging = true; 
        const touch = e.touches[0]; 
        startX = touch.clientX - currentX; 
        startY = touch.clientY - currentY; 
        captTrajectory = []; 
        e.preventDefault(); 
    }, {passive: false});
    
    window.addEventListener('touchend', e => { 
        if (!isCaptDragging) return; 
        isCaptDragging = false; 
        verifyCaptcha(); 
    });
    
    window.addEventListener('touchmove', e => {
        if (!isCaptDragging) return;
        const touch = e.touches[0];
        currentX = touch.clientX - startX; 
        currentY = touch.clientY - startY;
        captTrajectory.push({ x: currentX, y: currentY, t: Date.now() });
        renderCaptcha();
        e.preventDefault(); 
    }, {passive: false});

</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8, debug=False)
