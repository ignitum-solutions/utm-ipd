# Serverless deployment

The application uses a static React frontend and one streaming Python
Lambda. Local development does not need AWS. This guide is for maintainers;
researchers should use the setup in the repository README.

CloudFormation templates define the application (`infra/serverless.yaml`),
build storage and GitHub deployment role (`infra/deployment.yaml`), CloudFront
certificate (`infra/certificate.yaml`), and website DNS alias (`infra/dns.yaml`).
The existing shared Route 53 zone and GitHub OIDC provider remain account-level
prerequisites. Deploy the application in us-east-2 and its certificate in
us-east-1.

## Validate locally first

```bash
poetry install
npm --prefix frontend ci
poetry run pytest -q
npm --prefix frontend test
npm --prefix frontend run build
./run_local.sh
```

Verify all three simulations, progress, downloads, and the warning when leaving
an active run. Browser tests are documented in the README. A local test does
not verify CloudFront buffering, IAM origin restrictions, or AWS runtime limits.

## Bootstrap the infrastructure

Use an AWS region supporting Lambda Function URL response streaming. You need
Docker for the Lambda image build, AWS SAM CLI, AWS CLI, and an authorized AWS
profile or OIDC deployment role. The deployer needs the CloudFormation, IAM,
Lambda, ECR, S3, CloudFront, and logging permissions required by this template.
Do not put credentials, account-specific ARNs, or private data in the repository.

Use the generated CloudFront hostname to validate a new installation before
attaching a public hostname. Existing deployments can be updated in place.

Bootstrap the deployment identity and build storage with an authorized local
AWS profile. The template trusts only this repository's `main` branch; adjust
its parameters when using another repository or release branch.

```bash
aws cloudformation deploy --region us-east-2 --template-file infra/deployment.yaml \
  --stack-name utm-ipd-serverless-deployment --capabilities CAPABILITY_IAM
```

Set the GitHub repository secret `SERVERLESS_AWS_ROLE_ARN` to the bootstrap
stack's `DeployRoleArn` output. Set the secret `SERVERLESS_BUILD_ROLE_ARN` to its
`ImagePullRoleArn` output for authenticated CI image downloads, and set the
nonsensitive repository variable `SERVERLESS_BUILD_ENABLED=true`. This separate
role can obtain public image-pull tokens but cannot access the application,
deploy resources, or invoke Lambda. Fork pull requests run the Python, frontend,
and browser checks without AWS credentials; the image job runs for configured
internal pull requests and `main`. Set `AWS_ACCOUNT_ID` as a repository secret
so deployments verify the target account. The deployment role manages
application resources and build storage; it cannot change its own trust policy
or publish website DNS changes.

Actions logs in a public repository are public. Keep account-specific role
ARNs in secrets, which GitHub masks in logs. The workflows also mask AWS account
IDs and the deployment's bucket, registry, distribution, and protected-origin
identifiers. The public site URL and source revision remain visible. Do not
enable debug logging or print credentials. Masking cannot remove data from
logs of earlier runs; review existing logs separately when changing settings.

For a hostname change through the workflow, store the issued us-east-1 ACM
certificate ARN as the secret `SERVERLESS_CERTIFICATE_ARN` and supply
`domain_name` when dispatching. The certificate is not a workflow input because
inputs are public run metadata. Leaving `domain_name` empty retains the existing
hostname and certificate, even if the optional certificate secret is configured.

Use the bootstrap outputs `ArtifactBucket` and `ImageRepository` for manual
deployments:

```bash
sam build --template-file infra/serverless.yaml
sam deploy --stack-name utm-ipd-serverless --region us-east-2 \
  --s3-bucket YOUR_ARTIFACT_BUCKET --image-repository YOUR_IMAGE_REPOSITORY \
  --capabilities CAPABILITY_IAM --parameter-overrides BuildRevision=SOURCE_COMMIT
```

Use an application stack name such as `utm-ipd-serverless`. Initially leave
`DomainName` and `CertificateArn` empty. Keep the default concurrency and run
limits until AWS measurements justify changing them. SAM retains the bucket
if the stack is removed; submissions are not deleted by a stack rollback.

Set `BuildRevision` to the source commit used for the image so result exports
identify the deployed revision. The manual GitHub workflow supplies the commit
automatically; guided deployments otherwise default to `unrecorded`.

The manual GitHub workflow runs Python, frontend, browser, and template checks,
builds with SAM, and exercises all three simulation streams in the packaged
image with a read-only filesystem. After deployment it checks the AWS backend
before publishing the frontend, waits for distribution invalidation, checks the
published assets and revision, and verifies denied unsigned origin access.
The deployment stack name is the application stack name plus `-deployment`.

Run **Deploy serverless playground** from `main`, matching the deployment role's
OIDC trust policy.
Use the optional `source_ref` input for a specific source commit/tag, including
a known-good React release for rollback. A code push alone does not deploy.

The template defines the site bucket, function and IAM role, short-retention
logs, CloudFront distribution/OACs, and restricted invocation permissions.
It does not create queues, an application database, or a job service. Suggestions
are enabled by writing into a private `submissions/` prefix with a 180-day
lifecycle. Frontend assets live under `site/`, the only prefix CloudFront can
read. Review the submission retention policy before accepting suggestions.

## Upload the frontend

Read `WebsiteBucket`, `DistributionId`, `WebsiteUrl`, and `ProtectedFunctionUrl`
from the stack outputs. Substitute the bucket and distribution identifiers below:

```bash
npm --prefix frontend run build
aws s3 sync frontend/dist/ s3://YOUR_BUCKET/site/ --exclude index.html --cache-control 'public,max-age=300'
aws s3 cp frontend/dist/index.html s3://YOUR_BUCKET/site/index.html --cache-control 'no-cache' --content-type 'text/html'
aws cloudfront create-invalidation --distribution-id YOUR_DISTRIBUTION --paths '/*'
```

Keep old hashed assets during rollout so an already-open page can still load
its release. The manual GitHub deployment workflow performs these steps after
validation. It needs `SERVERLESS_AWS_ROLE_ARN` as a repository secret
and an explicit workflow dispatch.
Set `VITE_BUILD_REVISION=SOURCE_COMMIT` when building manually; the verification
script checks that the frontend and backend identify the same source revision.
The site bucket retains prior object versions, with noncurrent site versions
expiring after 30 days. Old hashed assets are not deleted during publication.

## Verify the deployed application

- Open `WebsiteUrl` and exercise tournament, Moran, and Trust Game runs.
- Observe progress arriving incrementally, including on a run over one minute;
  verify result downloads. Confirm a cold invocation does not exhaust the
  origin's initial response timeout.
- Check leave/stay behavior, a failed stream, timeout, and a busy response.
- An unsigned request directly to `ProtectedFunctionUrl` must return 403 before
  application execution. A different CloudFront distribution must not have
  permission. Validate signed POST bodies through the intended distribution.
- Confirm private submissions cannot be read through the frontend S3 origin.
- Review identity policies for unintended same-account Lambda invocation
  grants, in addition to the distribution-scoped resource permissions.
- Benchmark memory and maximum allowed inputs on the target architecture.
  Verify the request process terminates and emits an error before the Lambda
  timeout. Local process cleanup does not prove cancellation after a hosted
  viewer disconnect; the execution limit remains authoritative.

The same HTTP checks used by CI are available locally:

```bash
python scripts/verify_deployment.py --url https://YOUR_DISTRIBUTION.cloudfront.net \
  --revision SOURCE_COMMIT --protected-function-url https://YOUR_FUNCTION.lambda-url.us-east-2.on.aws/ \
  --bucket YOUR_BUCKET --region us-east-2
```

This performs small seeded runs and checks streamed event order and completed
results. Printed arrival times help inspect delivery; these small runs do not
replace the longer browser streaming check above. POST requests are not retried.

Function URLs and the Lambda Web Adapter both use response-stream mode. API
caching and compression are disabled. The CloudFront origin read timeout is
60 seconds; the backend sends heartbeats during execution. Response completion
timeout is omitted so it does not impose a shorter total run duration. The
engine defaults to a 240-second budget, at most 840 seconds, within Lambda's
900-second limit. Cold starts and return/cleanup need remaining time.

## Configure a custom hostname

1. Obtain or reuse a valid ACM certificate in us-east-1. For a dedicated
   DNS-validated certificate, deploy `infra/certificate.yaml` in us-east-1 with
   `DomainName` and the existing `HostedZoneId`. Update the new application stack
   with `DomainName` and `CertificateArn`; an alias already attached to an old
   CloudFront distribution must be moved using the appropriate AWS procedure.
2. Point the production DNS record at the distribution only after its
   certificate and alias are ready. Record the previous DNS target and image
   revision so rollback is concrete.
   `infra/dns.yaml` declares the desired alias and retains it if its stack is
   removed. An existing alias needs a deliberate ownership handover; a template
   cannot be assumed to import an existing record. Prepare and inspect the DNS
   change separately from ordinary application deployments.
3. Run production smoke tests through the public hostname, including streaming,
   downloads, revision matching, and unsigned origin access checks.

## Roll back a release

Dispatch the deployment workflow from `main` with `source_ref` set to a
known-good source commit or tag. The workflow builds and validates matching
frontend and backend versions from that revision. Keep the release source and
dependency lockfiles. DNS continues pointing at the same distribution during
an application rollback.

## Access boundary

CloudFront signs calls to an `AWS_IAM` Function URL. Only the configured
distribution receives service-principal invocation grants. A public browser
application still exposes its public request format; it cannot prove callers
are using the official React program. Workload validation and concurrency
limits reduce resource use without adding user accounts or shared admission
storage. Concurrency does not enforce a monthly or per-user quota.

AWS supports the URL-only `InvokedViaFunctionUrl` permission condition used here.
Older SAM/cfn-lint schemas may reject that valid property; use current schema
versions rather than removing the restriction to satisfy an outdated validator.

References: [response streaming](https://docs.aws.amazon.com/lambda/latest/dg/configuration-response-streaming.html),
[CloudFront OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html),
[permission properties](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lambda-permission.html).
