# Certificados HTTPS locais

Certificados reais e chaves privadas nao devem ser versionados.

Para desenvolvimento local, o proxy espera os arquivos:

```text
localhost.crt
localhost.key
```

Eles podem ser certificados self-signed criados localmente ou arquivos montados
por volume. O navegador pode exibir um aviso de seguranca ao usar um certificado
self-signed, o que e esperado apenas no ambiente local.

Em homologacao ou producao, use o certificado interno fornecido pela equipe de
infraestrutura/TI e mantenha os arquivos fora do Git.
