# Certificado ACM para la Evaluación 03

Esta etapa solicita el certificado público en `us-east-1` antes de aplicar el stack del ALB. Usa un estado independiente del stack principal y no modifica deSEC. Ejecuta estos pasos solo cuando la CLI del Learner Lab esté autenticada y tengas un FQDN bajo tu control. Si el dominio usa DNS delegado, comprueba que los servidores públicos sean los del proveedor antes de solicitar el certificado.

Desde la raíz del repositorio, en PowerShell:

```powershell
aws sts get-caller-identity --no-cli-pager
terraform -chdir=terraform/acm init
$env:TF_VAR_domain_name = Read-Host 'FQDN público exacto de la aplicación'
terraform -chdir=terraform/acm plan -out=acm.tfplan
```

Revisa que el plan solicite solo el certificado esperado y, si corresponde al Learner Lab, aplícalo:

```powershell
terraform -chdir=terraform/acm apply acm.tfplan
terraform -chdir=terraform/acm output -json validation_records
```

Publica en deSEC el CNAME que devuelve ACM. En el campo **Subname**, usa la parte de `name` relativa a la zona; como valor, conserva el destino completo. Comprueba que el registro resuelva en el DNS público. Luego consulta el estado:

```powershell
$arn = terraform -chdir=terraform/acm output -raw certificate_arn
aws acm describe-certificate --region us-east-1 --certificate-arn $arn --query 'Certificate.Status' --output text --no-cli-pager
```

Solo si devuelve `ISSUED`, usa `$arn` como `certificate_arn` y el mismo FQDN como `domain_name` en el stack principal. Conserva el CNAME de validación: ACM lo usa para renovar. El CNAME que apunta al ALB es un registro distinto y se publica después de crear el balanceador. Al desmontar el laboratorio, el stack principal se elimina primero para que el certificado deje de estar en uso.
