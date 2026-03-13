{{- define "ukde.image" -}}
{{- $root := .root -}}
{{- $service := .service -}}
{{- printf "%s/%s:%s" $root.Values.global.internalRegistry $service.image.repository (default $root.Values.global.imageTag $service.image.tag) -}}
{{- end -}}

{{- define "ukde.labels" -}}
app.kubernetes.io/name: ukde
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: ukde
app.kubernetes.io/environment: {{ .Values.global.environment | quote }}
ukde.io/deployment-class: {{ .Values.global.deploymentClass | quote }}
{{- end -}}

