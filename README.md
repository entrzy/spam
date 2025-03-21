
# HTTP Dialler Call - PowerShell GUI Application
# This application sends HTTP requests and displays responses in a web browser

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Net.Http
Add-Type -AssemblyName System.Web

# Create the main form
$form = New-Object System.Windows.Forms.Form
$form.Text = "HTTP Dialler Call"
$form.Size = New-Object System.Drawing.Size(600, 500)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
$form.MaximizeBox = $false

# URL Label
$urlLabel = New-Object System.Windows.Forms.Label
$urlLabel.Location = New-Object System.Drawing.Point(20, 20)
$urlLabel.Size = New-Object System.Drawing.Size(100, 20)
$urlLabel.Text = "URL:"
$form.Controls.Add($urlLabel)

# URL TextBox
$urlTextBox = New-Object System.Windows.Forms.TextBox
$urlTextBox.Location = New-Object System.Drawing.Point(120, 20)
$urlTextBox.Size = New-Object System.Drawing.Size(440, 20)
$urlTextBox.Text = "https://"
$form.Controls.Add($urlTextBox)

# HTTP Method Label
$methodLabel = New-Object System.Windows.Forms.Label
$methodLabel.Location = New-Object System.Drawing.Point(20, 60)
$methodLabel.Size = New-Object System.Drawing.Size(100, 20)
$methodLabel.Text = "HTTP Method:"
$form.Controls.Add($methodLabel)

# HTTP Method ComboBox
$methodComboBox = New-Object System.Windows.Forms.ComboBox
$methodComboBox.Location = New-Object System.Drawing.Point(120, 60)
$methodComboBox.Size = New-Object System.Drawing.Size(100, 20)
$methodComboBox.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
[void]$methodComboBox.Items.Add("GET")
[void]$methodComboBox.Items.Add("POST")
$methodComboBox.SelectedIndex = 0
$form.Controls.Add($methodComboBox)

# Headers Label
$headersLabel = New-Object System.Windows.Forms.Label
$headersLabel.Location = New-Object System.Drawing.Point(20, 100)
$headersLabel.Size = New-Object System.Drawing.Size(100, 20)
$headersLabel.Text = "HTTP Headers:"
$form.Controls.Add($headersLabel)

# Headers Description Label
$headersDescLabel = New-Object System.Windows.Forms.Label
$headersDescLabel.Location = New-Object System.Drawing.Point(120, 80)
$headersDescLabel.Size = New-Object System.Drawing.Size(440, 20)
$headersDescLabel.Text = "Enter one header per line in format: Header-Name: Value"
$headersDescLabel.Font = New-Object System.Drawing.Font("Arial", 8)
$form.Controls.Add($headersDescLabel)

# Headers TextBox (multiline)
$headersTextBox = New-Object System.Windows.Forms.TextBox
$headersTextBox.Location = New-Object System.Drawing.Point(120, 100)
$headersTextBox.Size = New-Object System.Drawing.Size(440, 100)
$headersTextBox.Multiline = $true
$headersTextBox.ScrollBars = "Vertical"
$headersTextBox.Text = "Content-Type: application/json`r`nAccept: */*"
$form.Controls.Add($headersTextBox)

# Request Body Label (only visible for POST)
$bodyLabel = New-Object System.Windows.Forms.Label
$bodyLabel.Location = New-Object System.Drawing.Point(20, 220)
$bodyLabel.Size = New-Object System.Drawing.Size(100, 20)
$bodyLabel.Text = "Request Body:"
$bodyLabel.Visible = $false
$form.Controls.Add($bodyLabel)

# Request Body TextBox (only visible for POST)
$bodyTextBox = New-Object System.Windows.Forms.TextBox
$bodyTextBox.Location = New-Object System.Drawing.Point(120, 220)
$bodyTextBox.Size = New-Object System.Drawing.Size(440, 150)
$bodyTextBox.Multiline = $true
$bodyTextBox.ScrollBars = "Vertical"
$bodyTextBox.Visible = $false
$form.Controls.Add($bodyTextBox)

# Body Type Label (only visible for POST)
$bodyTypeLabel = New-Object System.Windows.Forms.Label
$bodyTypeLabel.Location = New-Object System.Drawing.Point(20, 380)
$bodyTypeLabel.Size = New-Object System.Drawing.Size(100, 20)
$bodyTypeLabel.Text = "Body Type:"
$bodyTypeLabel.Visible = $false
$form.Controls.Add($bodyTypeLabel)

# Body Type ComboBox (only visible for POST)
$bodyTypeComboBox = New-Object System.Windows.Forms.ComboBox
$bodyTypeComboBox.Location = New-Object System.Drawing.Point(120, 380)
$bodyTypeComboBox.Size = New-Object System.Drawing.Size(200, 20)
$bodyTypeComboBox.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
[void]$bodyTypeComboBox.Items.Add("Raw (JSON/Text)")
[void]$bodyTypeComboBox.Items.Add("Form Data (x-www-form-urlencoded)")
$bodyTypeComboBox.SelectedIndex = 0
$bodyTypeComboBox.Visible = $false
$form.Controls.Add($bodyTypeComboBox)

# Event handler for method selection change
$methodComboBox.Add_SelectedIndexChanged({
    if ($methodComboBox.SelectedItem -eq "POST") {
        $bodyLabel.Visible = $true
        $bodyTextBox.Visible = $true
        $bodyTypeLabel.Visible = $true
        $bodyTypeComboBox.Visible = $true
        $sendButton.Location = New-Object System.Drawing.Point(240, 420)
        $statusLabel.Location = New-Object System.Drawing.Point(20, 460)
    } else {
        $bodyLabel.Visible = $false
        $bodyTextBox.Visible = $false
        $bodyTypeLabel.Visible = $false
        $bodyTypeComboBox.Visible = $false
        $sendButton.Location = New-Object System.Drawing.Point(240, 220)
        $statusLabel.Location = New-Object System.Drawing.Point(20, 260)
    }
    $form.Refresh()
})

# Send Button
$sendButton = New-Object System.Windows.Forms.Button
$sendButton.Location = New-Object System.Drawing.Point(240, 220)
$sendButton.Size = New-Object System.Drawing.Size(100, 30)
$sendButton.Text = "Send Request"
$form.Controls.Add($sendButton)

# Status Label
$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Location = New-Object System.Drawing.Point(20, 260)
$statusLabel.Size = New-Object System.Drawing.Size(540, 20)
$statusLabel.Text = "Ready"
$form.Controls.Add($statusLabel)

# Event handler for Send button click
$sendButton.Add_Click({
    $statusLabel.Text = "Sending request..."
    $form.Refresh()
    
    try {
        # Get URL from textbox
        $url = $urlTextBox.Text.Trim()
        if ([string]::IsNullOrEmpty($url)) {
            throw "URL cannot be empty"
        }
        
        # Validate URL format
        if (-not [System.Uri]::IsWellFormedUriString($url, [System.UriKind]::Absolute)) {
            throw "Invalid URL format. Please enter a valid URL including protocol (e.g., https://)"
        }
        
        # Parse headers
        $headers = @{}
        if (-not [string]::IsNullOrEmpty($headersTextBox.Text)) {
            $headersTextBox.Text.Split("`r`n") | ForEach-Object {
                if (-not [string]::IsNullOrEmpty($_)) {
                    $key, $value = $_.Split(':', 2)
                    if ($key -and $value) {
                        $headers[$key.Trim()] = $value.Trim()
                    }
                }
            }
        }
        
        # Create HTTP client with redirect handling
        $handler = New-Object System.Net.Http.HttpClientHandler
        $handler.AllowAutoRedirect = $true
        $handler.MaxAutomaticRedirections = 10
        $client = New-Object System.Net.Http.HttpClient($handler)
        
        # Add headers to the client
        foreach ($header in $headers.GetEnumerator()) {
            # Skip content-type for now as it will be added to the content
            if ($header.Key -ne "Content-Type") {
                $client.DefaultRequestHeaders.TryAddWithoutValidation($header.Key, $header.Value)
            }
        }
        
        # Send the request based on selected method
        $response = $null
        if ($methodComboBox.SelectedItem -eq "GET") {
            $response = $client.GetAsync($url).Result
        } else {
            # Determine content type
            $contentType = "application/json"
            if ($headers.ContainsKey("Content-Type")) {
                $contentType = $headers["Content-Type"]
            }
            
            $content = $null
            
            # Handle content based on selected body type
            if ($bodyTypeComboBox.SelectedItem -eq "Form Data (x-www-form-urlencoded)") {
                # Override content type for form data
                $contentType = "application/x-www-form-urlencoded"
                
                # Create dictionary for form values
                $formData = New-Object 'System.Collections.Generic.Dictionary[string,string]'
                
                # Parse form data (key=value format, one per line)
                $bodyTextBox.Text.Split("`r`n") | ForEach-Object {
                    if (-not [string]::IsNullOrEmpty($_)) {
                        $key, $value = $_.Split('=', 2)
                        if ($key -and $value) {
                            $formData.Add($key.Trim(), $value.Trim())
                        }
                    }
                }
                
                $content = New-Object System.Net.Http.FormUrlEncodedContent($formData)
            } else {
                # Raw body
                $content = New-Object System.Net.Http.StringContent($bodyTextBox.Text, [System.Text.Encoding]::UTF8, $contentType)
            }
            
            $response = $client.PostAsync($url, $content).Result
        }
        
        # Check if request was successful
        if (-not $response.IsSuccessStatusCode) {
            throw "HTTP Error: $($response.StatusCode) - $($response.ReasonPhrase)"
        }
        
        # Read the response content
        $responseContent = $response.Content.ReadAsStringAsync().Result
        
        # Create a temporary HTML file to display
        $tempFile = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.html'
        Set-Content -Path $tempFile -Value $responseContent -Encoding UTF8
        
        # Open the default browser with the response
        Start-Process $tempFile
        
        $statusLabel.Text = "Request successful. Response displayed in browser."
    }
    catch {
        $statusLabel.Text = "Error: $($_.Exception.Message)"
    }
    finally {
        if ($client) {
            $client.Dispose()
        }
    }
})

# Show the form
[void]$form.ShowDialog()
