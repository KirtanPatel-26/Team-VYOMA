/**
 * Next.js App Router API Route: /api/anomalies
 * GET: Filter and paginate retail anomalies
 * POST: Ingest telemetry from Edge CV devices and run Anomaly Engine
 */

import { NextRequest, NextResponse } from 'next/server';
import { getSupabaseServerClient } from '@/lib/supabaseClient';
import { AnomalyDetectionEngine } from '@/services/AnomalyDetectionEngine';
import { CVTelemetryFrame } from '@/types/anomaly';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const status = searchParams.get('status');
  const severity = searchParams.get('severity');
  const type = searchParams.get('type');
  const zoneId = searchParams.get('zoneId');
  const limit = parseInt(searchParams.get('limit') || '50', 10);
  const offset = parseInt(searchParams.get('offset') || '0', 10);

  const supabase = getSupabaseServerClient();
  let query = supabase
    .from('anomalies')
    .select('*', { count: 'exact' })
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1);

  if (status && status !== 'ALL') {
    query = query.eq('status', status);
  }
  if (severity && severity !== 'ALL') {
    query = query.eq('severity', severity);
  }
  if (type) {
    query = query.eq('anomaly_type', type);
  }
  if (zoneId) {
    query = query.eq('zone_id', zoneId);
  }

  const { data, count, error } = await query;

  if (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }

  return NextResponse.json({
    success: true,
    total: count || 0,
    offset,
    limit,
    anomalies: data,
  });
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const telemetry: CVTelemetryFrame = body.telemetry;

    if (!telemetry || !telemetry.cameraId) {
      return NextResponse.json(
        { success: false, error: 'Invalid payload: telemetry frame with cameraId is required.' },
        { status: 400 }
      );
    }

    const supabase = getSupabaseServerClient();
    const engine = new AnomalyDetectionEngine(supabase);

    // Fetch active zones & rules to configure engine
    const [zonesRes, rulesRes, stockRes] = await Promise.all([
      supabase.from('zones_config').select('*'),
      supabase.from('anomaly_trigger_rules').select('*'),
      supabase.from('products').select('id, minimum_stock'),
    ]);

    const erpStockMap = new Map<string, number>();
    (stockRes.data || []).forEach((p: any) => erpStockMap.set(p.id, p.minimum_stock * 3));
    engine.setErpExpectedStock(erpStockMap);

    engine.updateConfigurations(zonesRes.data || [], rulesRes.data || []);

    // Execute engine across all 13 anomaly rules
    const detectedAnomalies = await engine.processTelemetryFrame(
      telemetry,
      body.recentSales || [],
      body.recentLedger || []
    );

    return NextResponse.json({
      success: true,
      processedAt: new Date().toISOString(),
      anomaliesDetectedCount: detectedAnomalies.length,
      anomalies: detectedAnomalies,
    });
  } catch (err: any) {
    console.error('[API /api/anomalies POST] Error:', err);
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
