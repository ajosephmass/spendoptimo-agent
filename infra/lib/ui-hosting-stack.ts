import { Stack, StackProps, CfnOutput, RemovalPolicy } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cf from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3d from 'aws-cdk-lib/aws-s3-deployment';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cr from 'aws-cdk-lib/custom-resources';

export interface UiProps extends StackProps {
  apiUrl: string;
  apiKeyValue: string;
  cognitoDomain: string;
  userPoolClientId: string;
  userPoolId: string;
}

export class UiHostingStack extends Stack {
  constructor(scope: Construct, id: string, props: UiProps) {
    super(scope, id, props);

    const siteBucket = new s3.Bucket(this, 'SpendOptimoWebBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const oai = new cf.OriginAccessIdentity(this, 'SpendOptimoOAI');

    const dist = new cf.Distribution(this, 'SpendOptimoDist', {
      defaultRootObject: 'index.html',
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessIdentity(siteBucket, { originAccessIdentity: oai }),
        viewerProtocolPolicy: cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
    });

    // Allow CloudFront (OAI) to read from the bucket
    siteBucket.addToResourcePolicy(new iam.PolicyStatement({
      actions: ['s3:GetObject'],
      resources: [siteBucket.arnForObjects('*')],
      principals: [
        new iam.CanonicalUserPrincipal(
          oai.cloudFrontOriginAccessIdentityS3CanonicalUserId
        ),
      ],
    }));

    // Styled SPA with Cognito sign-in and chat
    const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1" /><title>SpendOptimo</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='28' fill='%2322c55e'/%3E%3Ctext x='32' y='39' font-size='28' text-anchor='middle' fill='%2309210f' font-family='Arial'%3ES%3C/text%3E%3C/svg%3E"/>
<style>
  :root{--bg:#0f172a;--card:#0b1220;--muted:#94a3b8;--accent:#22c55e;--text:#e5e7eb}
  *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#0b1220,#0f172a);font:16px system-ui;color:var(--text)}
  .container{max-width:900px;margin:40px auto;padding:0 20px}
  .hero{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
  .brand{font-weight:700;font-size:22px;letter-spacing:.3px}
  .card{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px}
  .row{display:flex;gap:12px;flex-wrap:wrap}
  textarea{width:100%;min-height:96px;border-radius:12px;border:1px solid rgba(255,255,255,.12);background:#0b1220;color:var(--text);padding:10px}
  button{background:var(--accent);color:#09210f;border:0;border-radius:10px;padding:10px 14px;font-weight:600;cursor:pointer}
  button.link{background:transparent;color:var(--text);border:1px solid rgba(255,255,255,.15)}
  .muted{color:var(--muted)}
  #log{white-space:pre-wrap;background:#0b1220;border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:12px;min-height:120px}
  .pill{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);padding:6px 10px;border-radius:999px;font-size:12px}
  .spacer{height:12px}
  hr{border:none;border-top:1px solid rgba(255,255,255,.08);margin:20px 0}
</style>
</head><body><div class="container">
  <div class="hero">
    <div class="brand">SpendOptimo</div>
    <div>
      <button id="signin" class="link">Sign in with Cognito</button>
      <button id="signout" class="link" style="display:none">Sign out</button>
    </div>
  </div>
  <div class="muted" id="who">Not signed in</div>
  <div class="spacer"></div>
  <div class="card">
    <div class="muted" style="margin-bottom:8px">Ask SpendOptimo</div>
    <textarea id="goal" placeholder="Find cost anomalies this week and propose fixes..."></textarea>
    <div class="row" style="margin-top:10px">
      <button id="send">Send</button>
      <div class="pill">API key + Cognito auth</div>
    </div>
  </div>
  <div class="spacer"></div>
  <div class="card">
    <div class="muted" style="margin-bottom:8px">Response</div>
    <div id="log"></div>
  </div>
</div>
  <script>
  var apiUrl = ${JSON.stringify((props as any).apiUrl)};
  if (apiUrl && apiUrl.charAt(apiUrl.length-1) === '/') { apiUrl = apiUrl.slice(0, -1); }
  var cognitoDomain = ${JSON.stringify((props as any).cognitoDomain)};
  var clientId = ${JSON.stringify((props as any).userPoolClientId)};
  var redirectUri = window.location.origin + '/';

  function parseHash(){
    try{
      if(window.location.hash && window.location.hash.indexOf('#') === 0){
        var p=new URLSearchParams(window.location.hash.substring(1));
        var id=p.get('id_token');
        var acc=p.get('access_token');
        if(id){ localStorage.setItem('id_token',id); }
        if(acc){ localStorage.setItem('access_token',acc); }
        if(id||acc){ history.replaceState({},document.title,window.location.pathname); }
      }
    }catch(e){ console.error('parseHash',e); }
  }
  parseHash();

  function updateUi(){
    var t=localStorage.getItem('id_token');
    var signin=document.getElementById('signin');
    var signout=document.getElementById('signout');
    var who=document.getElementById('who');
    if(signin) signin.style.display = t ? 'none' : '';
    if(signout) signout.style.display = t ? '' : 'none';
    if(who) who.textContent = t ? 'Signed in' : 'Not signed in';
  }
  updateUi();

  document.getElementById('signin').onclick = function(){
    var url = 'https://' + cognitoDomain + '/login?response_type=token&client_id=' + encodeURIComponent(clientId) + '&redirect_uri=' + encodeURIComponent(redirectUri) + '&scope=openid+email+profile';
    window.location.assign(url);
  };
  document.getElementById('signout').onclick = function(){
    localStorage.removeItem('id_token');
    localStorage.removeItem('access_token');
    updateUi();
  };
  document.getElementById('send').onclick = function(){
    (async function(){
      try{
        var token = localStorage.getItem('id_token');
        if(!token){ alert('Please sign in first.'); return; }
        var el = document.getElementById('goal');
        var v = el && el.value ? el.value : '';
        var goal = (typeof v === 'string' ? v : '').trim();
        if(!goal){ alert('Enter a goal.'); return; }
        var r = await fetch(apiUrl + '/v1/chat', {
          method:'POST',
          headers:{ 'Content-Type':'application/json', 'Authorization':'Bearer ' + token },
          body: JSON.stringify({ goal: goal })
        });
        var text = await r.text();
        var logEl = document.getElementById('log'); if(logEl){ logEl.textContent = text; }
      }catch(e){ console.error(e); alert('Request failed; see console'); }
    })();
  };
  </script>
</body></html>`;

    new s3d.BucketDeployment(this, 'DeployIndex', {
      destinationBucket: siteBucket,
      distribution: dist,
      sources: [s3d.Source.data('index.html', html)],
    });

    // Auto-configure Cognito callback/logout URLs to this CloudFront domain
    const callbackUrl = 'https://' + dist.domainName + '/';
    new cr.AwsCustomResource(this, 'UpdateCognitoAppClient', {
      onUpdate: {
        service: 'CognitoIdentityServiceProvider',
        action: 'updateUserPoolClient',
        parameters: {
          UserPoolId: (props as any).userPoolId,
          ClientId: (props as any).userPoolClientId,
          AllowedOAuthFlowsUserPoolClient: true,
          AllowedOAuthFlows: ['implicit'],
          AllowedOAuthScopes: ['openid','email','profile'],
          CallbackURLs: [callbackUrl],
          LogoutURLs: [callbackUrl],
          SupportedIdentityProviders: ['COGNITO'],
        },
        physicalResourceId: cr.PhysicalResourceId.of('cognito-app-client-callback-' + dist.distributionId),
      },
      policy: cr.AwsCustomResourcePolicy.fromSdkCalls({ resources: cr.AwsCustomResourcePolicy.ANY_RESOURCE }),
    });

    new CfnOutput(this, 'CdnUrl', { value: 'https://' + dist.domainName });
    new CfnOutput(this, 'BucketName', { value: siteBucket.bucketName });
  }
}
