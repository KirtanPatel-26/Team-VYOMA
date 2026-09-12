/**
 * Next.js App Router API Route: /api/anomalies/[id]/acknowledge
 * PATCH: Acknowledge an active anomaly
 */

import { NextRequest, NextResponse } from 'next/server';
import { getSupabaseServerClient } from '@/lib/supabaseClient';
import { AlertService } from '@/services/AlertService';

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const anomalyId = params.id;
    const body = await req.json();
    const operatorName = body.operatorName || 'Store Manager';

    const supabase = getSupabaseServerClient();
    const alertService = new AlertService(supabase);

    const success = await alertService.acknowledgeAlert(anomalyId, operatorName);

    if (!success) {
      return NextResponse.json(
        { success: false, error: 'Failed to acknowledge anomaly' },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      anomalyId,
      status: 'Acknowledged',
      acknowledged_by: operatorName,
      acknowledged_at: new Date().toISOString(),
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
