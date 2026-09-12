/**
 * Next.js App Router API Route: /api/anomalies/[id]/resolve
 * PATCH: Resolve an anomaly with audit notes
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
    const notes = body.notes || 'Resolved by floor manager';

    const supabase = getSupabaseServerClient();
    const alertService = new AlertService(supabase);

    const success = await alertService.resolveAlert(anomalyId, operatorName, notes);

    if (!success) {
      return NextResponse.json(
        { success: false, error: 'Failed to resolve anomaly' },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      anomalyId,
      status: 'Resolved',
      resolved_by: operatorName,
      resolution_notes: notes,
      resolved_at: new Date().toISOString(),
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
