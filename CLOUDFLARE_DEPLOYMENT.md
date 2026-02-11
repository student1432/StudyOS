# StudyOS Cloudflare Deployment Guide

## Overview
Cloudflare doesn't natively support Python Flask applications. For a full-stack Flask app with Firebase, we recommend a **hybrid deployment approach**:

1. Deploy Flask app to a Python-compatible platform (Render, Railway, etc.)
2. Use Cloudflare as CDN, DNS, and security layer

## Option 1: Hybrid Deployment (Recommended)

### Step 1: Deploy Flask App to Primary Platform

**Choose one of these platforms:**

#### A) Render (Free tier available)
```bash
# 1. Create account at render.com
# 2. Connect your GitHub repository
# 3. Create new Web Service
# 4. Configure build settings:
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
# 5. Add environment variables in Render dashboard
```

#### B) Railway (Alternative)
```bash
# 1. Create account at railway.app
# 2. Connect GitHub repo
# 3. Deploy automatically
# 4. Add environment variables
```

### Step 2: Configure Cloudflare

#### A) Add Your Domain to Cloudflare
```bash
# 1. Sign up at cloudflare.com
# 2. Add your domain
# 3. Update nameservers at your domain registrar
```

#### B) Create DNS Records
```
Type: CNAME
Name: @
Content: your-render-app.onrender.com (or railway URL)
TTL: Auto
```

#### C) SSL/TLS Configuration
```
SSL/TLS encryption mode: Full (strict)
Always Use HTTPS: On
```

#### D) Speed Optimizations
```
- Enable Auto Minify (HTML, CSS, JS)
- Enable Brotli compression
- Enable HTTP/2 and HTTP/3
- Enable 0-RTT Connection Resumption
```

### Step 3: Security & Performance

#### WAF Rules (Web Application Firewall)
```javascript
// Create custom rules for your app
- Block common attacks
- Rate limiting per IP
- Country blocking if needed
```

#### Page Rules (for static assets)
```
URL: yourdomain.com/static/*
Cache Level: Cache Everything
Edge Cache TTL: 1 year
Browser Cache TTL: 1 year
```

### Step 4: Environment Variables

**Set these in both your deployment platform AND Cloudflare:**

```bash
# Required for Flask app
FLASK_ENV=production
SECRET_KEY=your-secret-key
PORT=10000 (or whatever your platform assigns)

# Firebase
FIREBASE_CREDENTIALS_PATH=/path/to/serviceAccountKey.json
GEMINI_API_KEY=your-gemini-key

# Email (optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

## Option 2: Cloudflare Workers (Limited)

### Requirements
- Wrangler CLI: `npm install -g wrangler`
- Python support in Cloudflare Workers is limited

### Step 1: Convert Flask Routes to Worker Functions
```javascript
// Not recommended for full Flask app
// Better for API-only endpoints
```

**Note:** Cloudflare Workers with Python support is in beta and may not support all Flask features.

## Option 3: Cloudflare Pages + Functions (Static Frontend)

### Step 1: Separate Frontend and Backend

**Move static templates to Pages:**
```
/pages
  - landing.html
  - login.html
  - signup.html
  - dashboard.html (static version)
```

### Step 2: Create API Routes in Functions
```javascript
// functions/api/login.js
export async function onRequestPost(context) {
  // Handle login logic
}
```

### Step 3: Deploy Pages
```bash
# 1. Install Wrangler: npm install -g wrangler
# 2. Login: wrangler auth login
# 3. Init: wrangler pages dev
# 4. Deploy: wrangler pages deploy
```

## Configuration Files

### _headers (for Pages)
```
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: geolocation=(), microphone=(), camera=()

/api/*
  Access-Control-Allow-Origin: https://yourdomain.com
  Access-Control-Allow-Methods: GET, POST, PUT, DELETE
  Access-Control-Allow-Headers: Content-Type, Authorization
```

### _redirects (for Pages)
```
/api/*  https://your-backend-url.com/api/:splat  200
/*      /index.html   200
```

## Monitoring & Analytics

### Cloudflare Analytics
- Real-time traffic monitoring
- Security events
- Performance metrics

### Error Tracking
```javascript
// Add to your Flask app
@app.errorhandler(500)
def internal_error(error):
    # Log to external service
    return render_template('500.html'), 500
```

## Cost Comparison

| Platform | Free Tier | Paid Plan |
|----------|-----------|-----------|
| Render | 750hrs/month | $7/month |
| Railway | $5/month credit | $5+/month |
| Cloudflare | Always free | Free for most features |

## Troubleshooting

### Common Issues:

1. **SSL Errors**: Check SSL/TLS settings in Cloudflare
2. **CORS Issues**: Configure CORS headers properly
3. **Caching Problems**: Purge cache or adjust cache rules
4. **Environment Variables**: Ensure all vars are set in both platforms

### Debug Commands:
```bash
# Check DNS propagation
nslookup yourdomain.com

# Test SSL
openssl s_client -connect yourdomain.com:443

# Check Cloudflare status
curl -H "CF-RAY: 1" https://yourdomain.com
```

## Security Best Practices

1. **Enable WAF**: Web Application Firewall
2. **Rate Limiting**: Protect against abuse
3. **DDoS Protection**: Automatic with Cloudflare
4. **SSL/TLS**: Always use HTTPS
5. **Security Headers**: Implement proper headers

## Performance Optimization

1. **CDN**: Automatic global distribution
2. **Caching**: Cache static assets aggressively
3. **Compression**: Enable Brotli and Gzip
4. **Image Optimization**: Use Cloudflare Images
5. **Bot Management**: Protect against bad bots

---

## Quick Start (Hybrid Approach)

1. **Deploy to Render:**
   - Create Render account
   - Connect GitHub repo
   - Add environment variables
   - Deploy

2. **Setup Cloudflare:**
   - Add domain to Cloudflare
   - Point DNS to Render app
   - Enable SSL and optimizations

3. **Configure Security:**
   - Enable WAF rules
   - Set up rate limiting
   - Configure firewall rules

**Your StudyOS app will be live with global CDN, SSL, and advanced security!** 🚀
