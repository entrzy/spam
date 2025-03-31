ent  <system.diagnostics>
    <trace autoflush="true" indentsize="4">
      <listeners>
        <remove name="Default"/>
        <add 
          name="FileListener" 
          type="System.Diagnostics.TextWriterTraceListener" 
          initializeData="C:\Logs\OrchestratorTrace.log" />
      </listeners>
    </trace>
    <sources>
      <!-- Włącz śledzenie dla System.IdentityModel i Microsoft.IdentityModel, 
           które odpowiadają m.in. za logikę SAML/ADFS -->
      <source name="System.IdentityModel" switchName="SAMLTraceSwitch">
        <listeners>
          <add name="FileListener" />
        </listeners>
      </source>
      <source name="Microsoft.IdentityModel" switchName="SAMLTraceSwitch">
        <listeners>
          <add name="FileListener" />
        </listeners>
      </source>
      <!-- Opcjonalnie włącz też System.Net, jeśli chcesz widzieć niskopoziomowy ruch HTTP -->
      <source name="System.Net" switchName="SAMLTraceSwitch">
        <listeners>
          <add name="FileListener" />
        </listeners>
      </source>
    </sources>
    <switches>
      <add name="SAMLTraceSwitch" value="Verbose"/>
    </switches>
  </system.diagnostics>

  <system.identityModel>
    <diagnostics>
      <traceLevel>Verbose</traceLevel>
      <traceMode>All</traceMode>
    </diagnostics>
  </system.identityModel>
