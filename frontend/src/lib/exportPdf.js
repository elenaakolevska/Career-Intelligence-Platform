export async function exportOverviewPdf() {
  const el = document.getElementById('overview-export')
  if (!el) throw new Error('Overview content not found')

  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
    import('html2canvas'),
    import('jspdf'),
  ])

  const canvas = await html2canvas(el, {
    scale: 2,
    useCORS: true,
    backgroundColor: '#ffffff',
    logging: false,
  })

  const img = canvas.toDataURL('image/png')
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  const pageW = pdf.internal.pageSize.getWidth()
  const pageH = pdf.internal.pageSize.getHeight()
  const margin = 10
  const usableW = pageW - margin * 2
  const pageContentH = pageH - margin * 2
  const imgH = (canvas.height * usableW) / canvas.width

  let heightLeft = imgH
  let offset = 0

  pdf.addImage(img, 'PNG', margin, margin, usableW, imgH)
  heightLeft -= pageContentH

  while (heightLeft > 0) {
    offset -= pageContentH
    pdf.addPage()
    pdf.addImage(img, 'PNG', margin, offset + margin, usableW, imgH)
    heightLeft -= pageContentH
  }

  const date = new Date().toISOString().slice(0, 10)
  pdf.save(`skillbridge-overview-${date}.pdf`)
}
